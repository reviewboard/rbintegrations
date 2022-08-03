"""Unit tests for the Travis CI integration."""

import json
from urllib.error import HTTPError

from django.urls import reverse
from djblets.conditions import ConditionSet, Condition
from reviewboard.hostingsvcs.models import HostingServiceAccount
from reviewboard.hostingsvcs.service import (HostingServiceHTTPRequest,
                                             HostingServiceHTTPResponse)
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice
from reviewboard.reviews.models import StatusUpdate
from reviewboard.reviews.signals import status_update_request_run

from rbintegrations.travisci.api import TravisAPI
from rbintegrations.travisci.forms import TravisCIIntegrationConfigForm
from rbintegrations.travisci.integration import TravisCIIntegration
from rbintegrations.travisci.views import TravisCIWebHookView
from rbintegrations.testing.testcases import IntegrationTestCase


class BaseTravisCITestCase(IntegrationTestCase):
    """Base class for Travis CI tests."""

    integration_cls = TravisCIIntegration
    fixtures = ['test_scmtools', 'test_users']

    def _create_repository(self, github=True, repository_plan='public-org'):
        """Create and return a repository for testing.

        Args:
            github (bool, optional):
                Whether the repository should use the GitHub hosting service.

            repository_plan (unicode, optional):
                The type of GitHub repository plan.

        Returns:
            reviewboard.scmtools.models.Repository:
            A repository for use in unit tests.
        """
        if github:
            account = HostingServiceAccount(service_name='github',
                                            username='myuser')

            def _http_get_user(_self, url, *args, **kwargs):
                self.assertEqual(url, 'https://api.github.com/user')

                payload = b'{}'
                headers = {
                    str('X-OAuth-Scopes'): str('admin:repo_hook, repo, user'),
                }

                return HostingServiceHTTPResponse(
                    request=HostingServiceHTTPRequest(url=url),
                    url=url,
                    data=payload,
                    headers=headers,
                    status_code=200)

            service = account.service
            self.spy_on(service.client.http_get,
                        call_fake=_http_get_user)

            service.authorize('myuser', 'mypass', None)
            self.assertTrue(account.is_authorized)

            service.client.http_get.unspy()

            repository = self.create_repository()
            repository.hosting_account = account
            repository.extra_data['repository_plan'] = repository_plan

            if repository_plan == 'public':
                repository.extra_data['github_public_repo_name'] = \
                    'mypublicrepo'
            elif repository_plan == 'public-org':
                repository.extra_data['github_public_org_name'] = 'mypublicorg'
                repository.extra_data['github_public_org_repo_name'] = \
                    'mypublicorgrepo'
            elif repository_plan == 'private':
                repository.extra_data['github_private_repo_name'] = \
                    'myprivaterepo'
            elif repository_plan == 'private-org':
                repository.extra_data['github_private_org_name'] = \
                    'myprivateorg'
                repository.extra_data['github_private_org_repo_name'] = \
                    'myprivateorgrepo'

            repository.save()
            return repository
        else:
            return self.create_repository()

    def _create_config(self, enterprise=False, with_local_site=False,
                       run_manually=False):
        """Create an integration config.

        Args:
            enterprise (bool, optional):
                Whether to use an enterprise endpoint or the default
                open-source endpoint.

            with_local_site (bool, optional):
                Whether to limit the config to a local site.
        """
        choice = ReviewRequestRepositoriesChoice()

        condition_set = ConditionSet(conditions=[
            Condition(choice=choice,
                      operator=choice.get_operator('any'))
        ])

        if with_local_site:
            local_site = self.get_local_site(name=self.local_site_name)
        else:
            local_site = None

        config = self.integration.create_config(name='Config 1',
                                                enabled=True,
                                                local_site=local_site)
        config.set('conditions', condition_set.serialize())
        config.set('travis_yml', 'script:\n    python ./tests/runtests.py')
        config.set('branch_name', 'review-requests')
        config.set('run_manually', run_manually)

        if enterprise:
            config.set('travis_endpoint', TravisAPI.ENTERPRISE_ENDPOINT)
            config.set('travis_custom_endpoint', 'https://travis.example.com/')
        else:
            config.set('travis_endpoint', TravisAPI.OPEN_SOURCE_ENDPOINT)

        config.save()

        return config

    def _spy_on_make_request(self):
        """Wrapper function for spying on the urlopen function.

        Returns:
            dict:
            Faked response from TravisCI.
        """
        data = {}

        def _make_request(api, url, body=None, method='GET', headers={},
                          content_type=None):
            # We can't actually do any assertions in here, because they'll get
            # swallowed by SignalHook's sandboxing. We therefore record the
            # data we need and assert later.
            data['url'] = url
            data['request'] = json.loads(body)['request']
            return '{}'

        self.spy_on(TravisAPI._make_request, owner=TravisAPI,
                    call_fake=_make_request)

        return data


class TravisCIIntegrationTests(BaseTravisCITestCase):
    """Tests for Travis CI."""

    def test_build_new_review_request(self):
        """Testing TravisCIIntegration builds a new review request"""
        repository = self._create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        config = self._create_config()
        self.integration.enable_integration()

        data = self._spy_on_make_request()

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://api.travis-ci.org/repo/mypublicorg%2Fmypublicorgrepo/'
            'requests')

        self.assertEqual(
            data['request']['config']['env']['global'],
            [
                'REVIEWBOARD_STATUS_UPDATE_ID=1',
                'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d' % config.pk,
            ])

        self.assertEqual(data['request']['message'],
                         'Test Summary\n\nTest Description')
        self.assertTrue('git fetch --unshallow origin || true'
                        in data['request']['config']['before_install'])
        self.assertTrue('git checkout %s' % diffset.base_commit_id
                        in data['request']['config']['before_install'])
        self.assertEqual(data['request']['branch'], 'review-requests')

    def test_build_new_review_request_on_enterprise_travis(self):
        """Testing TravisCIIntegration builds a new review request with Travis
        CI Enterprise
        """
        repository = self._create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        config = self._create_config(enterprise=True)
        self.integration.enable_integration()

        data = self._spy_on_make_request()

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://travis.example.com/api/repo/'
            'mypublicorg%2Fmypublicorgrepo/requests')

        self.assertEqual(
            data['request']['config']['env']['global'],
            [
                'REVIEWBOARD_STATUS_UPDATE_ID=1',
                'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d' % config.pk,
            ])
        self.assertEqual(data['request']['message'],
                         'Test Summary\n\nTest Description')
        self.assertTrue('git checkout %s' % diffset.base_commit_id
                        in data['request']['config']['before_install'])
        self.assertEqual(data['request']['branch'], 'review-requests')

    def test_build_new_review_request_with_parent_diff(self):
        """Testing TravisCIIntegration build script with a parent diff"""
        repository = self._create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        filediff = self.create_filediff(diffset)
        filediff.parent_diff = (
            b'--- README\trevision 123\n'
            b'+++ README\trevision 123\n'
            b'@@ -1 +1 @@\n'
            b'-Hello, world!\n'
            b'+Hello, everybody!\n'
        )
        filediff.save()

        config = self._create_config(enterprise=True)
        self.integration.enable_integration()

        data = self._spy_on_make_request()

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://travis.example.com/api/repo/'
            'mypublicorg%2Fmypublicorgrepo/requests')

        self.assertEqual(
            data['request']['config']['env']['global'],
            [
                'REVIEWBOARD_STATUS_UPDATE_ID=1',
                'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d' % config.pk,
            ])
        self.assertEqual(data['request']['message'],
                         'Test Summary\n\nTest Description')
        self.assertTrue('git checkout %s' % diffset.base_commit_id
                        in data['request']['config']['before_install'])
        self.assertEqual(data['request']['branch'], 'review-requests')

        patch_count = len(
            [cmd for cmd in data['request']['config']['before_install']
             if 'patch -p1' in cmd])

        self.assertEqual(patch_count, 2)

    def test_build_new_review_request_with_git_depth(self):
        """Testing TravisCIIntegration builds with git: depth: False"""
        repository = self._create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        config = self._create_config()
        config.set('travis_yml',
                   'git:\n'
                   '    depth:\n'
                   '        False\n'
                   '\n'
                   'script:\n'
                   '    python ./tests/runtests.py')
        config.save()
        self.integration.enable_integration()

        data = self._spy_on_make_request()

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://api.travis-ci.org/repo/mypublicorg%2Fmypublicorgrepo/'
            'requests')

        self.assertEqual(
            data['request']['config']['env']['global'],
            [
                'REVIEWBOARD_STATUS_UPDATE_ID=1',
                'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d' % config.pk,
            ])
        self.assertEqual(data['request']['message'],
                         'Test Summary\n\nTest Description')
        self.assertFalse('git fetch --unshallow origin || true'
                         in data['request']['config']['before_install'])
        self.assertEqual(data['request']['branch'], 'review-requests')

    def test_non_github_review_request(self):
        """Testing TravisCIIntegration skipping a non-GitHub review request"""
        repository = self._create_repository(github=False)
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(TravisAPI._make_request, owner=TravisAPI,
                    call_original=False)

        review_request.publish(review_request.submitter)

        self.assertFalse(TravisAPI._make_request.called)

    def test_travisci_config_form_valid(self):
        """Testing TravisCIIntegrationConfigForm validation success"""
        form = TravisCIIntegrationConfigForm(
            integration=self.integration,
            request=None,
            data={
                'conditions_last_id': 0,
                'conditions_mode': 'always',
                'name': 'test',
                'travis_endpoint': TravisAPI.OPEN_SOURCE_ENDPOINT,
                'travis_ci_token': '123456',
                'travis_yml': 'script:\n    - python ./tests/runtests.py',
            })

        self.spy_on(TravisAPI.get_user, owner=TravisAPI, call_original=False)
        self.spy_on(TravisAPI.lint,
                    owner=TravisAPI,
                    call_fake=lambda x, travis_yml: {'warnings': []})

        self.assertTrue(form.is_valid())

    def test_travisci_config_form_lint_failure(self):
        """Testing TravisCIIntegrationConfigForm validation lint failure"""
        self.spy_on(TravisAPI.get_user, owner=TravisAPI, call_original=False)
        self.spy_on(
            TravisAPI.lint,
            owner=TravisAPI,
            call_fake=lambda x, travis_yml: {
                'warnings': [{
                    'key': 'script',
                    'message': 'An error',
                }],
            })

        form = TravisCIIntegrationConfigForm(
            integration=self.integration,
            request=None,
            data={
                'conditions_last_id': 0,
                'conditions_mode': 'always',
                'name': 'test',
                'travis_endpoint': TravisAPI.OPEN_SOURCE_ENDPOINT,
                'travis_ci_token': '123456',
                'travis_yml': 'script:\n    - python ./tests/runtests.py',
            })

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['travis_yml'],
                         ['In script section: An error'])

    def test_travisci_config_form_auth_failure(self):
        """Testing TravisCIIntegrationConfigForm config validation"""
        def _raise_403(obj):
            raise HTTPError('', 403, 'Authentication failed', None, None)

        self.spy_on(TravisAPI.get_user, owner=TravisAPI, call_fake=_raise_403)

        form = TravisCIIntegrationConfigForm(
            integration=self.integration,
            request=None,
            data={
                'conditions_last_id': 0,
                'conditions_mode': 'always',
                'name': 'test',
                'travis_endpoint': TravisAPI.OPEN_SOURCE_ENDPOINT,
                'travis_ci_token': '123456',
                'travis_yml': 'script:\n    - python ./tests/runtests.py',
            })

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['travis_ci_token'],
                         ['Unable to authenticate with this API token.'])

    def test_manual_run_no_build_on_publish(self):
        """Testing lack of TravisCIIntegration build when a new review
        request is made with the run manually configuration
        """
        repository = self._create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config(run_manually=True)
        self.integration.enable_integration()

        data = self._spy_on_make_request()

        review_request.publish(review_request.submitter)

        self.assertFalse(TravisAPI._make_request.called)

        self.assertEqual(data, {})

    def test_build_manual_run(self):
        """Testing TravisCIIntegration build via a manual trigger"""
        repository = self._create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        config = self._create_config()
        self.integration.enable_integration()

        status_update = \
            self.create_status_update(service_id='travis-ci',
                                      review_request=review_request)

        data = self._spy_on_make_request()

        status_update_request_run.send(sender=self.__class__,
                                       status_update=status_update)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://api.travis-ci.org/repo/'
            'mypublicorg%2Fmypublicorgrepo/requests')

        self.assertEqual(
            data['request']['config']['env']['global'],
            [
                'REVIEWBOARD_STATUS_UPDATE_ID=1',
                'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d' % config.pk,
            ])

        self.assertEqual(data['request']['message'],
                         'Test Summary\n\nTest Description')
        self.assertTrue('git fetch --unshallow origin || true'
                        in data['request']['config']['before_install'])
        self.assertTrue('git checkout %s' % diffset.base_commit_id
                        in data['request']['config']['before_install'])
        self.assertEqual(data['request']['branch'], 'review-requests')

    def test_build_new_review_request_with_public_github_repository(self):
        """Testing CircleCIIntegration builds for a new review request with
        a public GitHub repository
        """
        repository = self._create_repository(repository_plan='public')
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        data = self._spy_on_make_request()

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://api.travis-ci.org/repo/myuser%2Fmypublicrepo/requests')

    def test_build_new_review_request_with_private_github_repository(self):
        """Testing CircleCIIntegration builds for a new review request with
        a public GitHub repository
        """
        repository = self._create_repository(repository_plan='private')
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        data = self._spy_on_make_request()

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://api.travis-ci.org/repo/myuser%2Fmyprivaterepo/requests')

    def test_build_new_review_request_with_private_org_github_repository(self):
        """Testing CircleCIIntegration builds for a new review request with
        a public GitHub repository
        """
        repository = self._create_repository(repository_plan='private-org')
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        data = self._spy_on_make_request()

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://api.travis-ci.org/repo/'
            'myprivateorg%2Fmyprivateorgrepo/requests')


class TravisCIWebHookTests(BaseTravisCITestCase):
    """Tests for the Travis CI webhook handler."""

    def setUp(self):
        super(TravisCIWebHookTests, self).setUp()

        self.repository = self._create_repository()
        self.review_request = self.create_review_request(
            repository=self.repository)

        self.status_update = self.create_status_update(self.review_request)

        self.config = self._create_config()
        self.integration.enable_integration()

        self.webhook_url = reverse('travis-ci-webhook')

    def test_webhook_no_env(self):
        """Testing TravisCIWebHookView with missing env"""
        payload = json.dumps({})
        rsp = self.client.post(self.webhook_url, {'payload': payload})

        self.assertEqual(rsp.status_code, 400)
        self.assertEqual(rsp.content, b'Got event without an env in config.')

    def test_webhook_missing_ids(self):
        """Testing TravisCIWebHookView with missing object IDs"""
        payload = json.dumps({
            'matrix': [
                {
                    'config': {
                        'env': [
                            'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d'
                            % self.config.pk,
                        ],
                    },
                },
            ],
        })
        rsp = self.client.post(self.webhook_url, {'payload': payload})

        self.assertEqual(rsp.status_code, 400)
        self.assertEqual(
            rsp.content,
            b'Unable to find REVIEWBOARD_STATUS_UPDATE_ID in payload.')

        payload = json.dumps({
            'matrix': [
                {
                    'config': {
                        'env': [
                            'REVIEWBOARD_STATUS_UPDATE_ID=%d'
                            % self.status_update.pk,
                        ],
                    },
                },
            ],
        })
        rsp = self.client.post(self.webhook_url, {'payload': payload})

        self.assertEqual(rsp.status_code, 400)
        self.assertEqual(
            rsp.content,
            b'Unable to find REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID in '
            b'payload.')

    def test_webhook_bad_integration_config(self):
        """Testing TravisCIWebHookView with incorrect integration config ID"""
        payload = json.dumps({
            'matrix': [
                {
                    'config': {
                        'env': [
                            'REVIEWBOARD_STATUS_UPDATE_ID=%d'
                            % self.status_update.pk,
                            'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d'
                            % (self.config.pk + 1),
                        ],
                    },
                },
            ],
        })
        rsp = self.client.post(self.webhook_url, {'payload': payload})

        self.assertEqual(rsp.status_code, 400)
        self.assertEqual(
            rsp.content,
            b'Unable to find matching integration config ID %d.'
            % (self.config.pk + 1))

    def test_webhook_bad_signature(self):
        """Testing TravisCIWebHookView with bad HTTP_SIGNATURE"""
        payload = json.dumps({
            'matrix': [
                {
                    'config': {
                        'env': [
                            'REVIEWBOARD_STATUS_UPDATE_ID=%d'
                            % self.status_update.pk,
                            'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d'
                            % self.config.pk,
                        ],
                    },
                },
            ],
        })
        rsp = self.client.post(self.webhook_url, {'payload': payload})

        self.assertEqual(rsp.status_code, 400)
        self.assertEqual(
            rsp.content,
            b'Invalid Travis CI webhook signature for status update %d.'
            % self.status_update.pk)

    def test_webhook_bad_status_update(self):
        """Testing TravisCIWebHookView with incorrect status update ID"""
        payload = json.dumps({
            'matrix': [
                {
                    'config': {
                        'env': [
                            'REVIEWBOARD_STATUS_UPDATE_ID=%d'
                            % (self.status_update.pk + 1),
                            'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d'
                            % self.config.pk,
                        ],
                    },
                },
            ],
        })
        self.spy_on(TravisCIWebHookView._validate_signature,
                    owner=TravisCIWebHookView,
                    call_fake=lambda self, request, integration_config: True)

        rsp = self.client.post(self.webhook_url, {'payload': payload})

        self.assertEqual(rsp.status_code, 400)
        self.assertEqual(
            rsp.content,
            b'Unable to find matching status update ID %d.'
            % (self.status_update.pk + 1))

    def test_webhook_build_pending(self):
        """Testing TravisCIWebHookView build pending"""
        payload = json.dumps({
            'matrix': [
                {
                    'config': {
                        'env': [
                            'REVIEWBOARD_STATUS_UPDATE_ID=%d'
                            % self.status_update.pk,
                            'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d'
                            % self.config.pk,
                        ],
                    },
                },
            ],
            'build_url': 'https://example.com/build',
            'state': 'started',
        })
        self.spy_on(TravisCIWebHookView._validate_signature,
                    owner=TravisCIWebHookView,
                    call_fake=lambda self, request, integration_config: True)

        rsp = self.client.post(self.webhook_url, {'payload': payload})

        self.assertEqual(rsp.status_code, 200)

        self.status_update = StatusUpdate.objects.get(pk=self.status_update.pk)
        self.assertEqual(self.status_update.url, 'https://example.com/build')
        self.assertEqual(self.status_update.state,
                         StatusUpdate.PENDING)

    def test_webhook_build_success(self):
        """Testing TravisCIWebHookView build success"""
        payload = json.dumps({
            'matrix': [
                {
                    'config': {
                        'env': [
                            'REVIEWBOARD_STATUS_UPDATE_ID=%d'
                            % self.status_update.pk,
                            'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d'
                            % self.config.pk,
                        ],
                    },
                },
            ],
            'build_url': 'https://example.com/build',
            'state': 'passed',
        })
        self.spy_on(TravisCIWebHookView._validate_signature,
                    owner=TravisCIWebHookView,
                    call_fake=lambda self, request, integration_config: True)

        rsp = self.client.post(self.webhook_url, {'payload': payload})

        self.assertEqual(rsp.status_code, 200)

        self.status_update = StatusUpdate.objects.get(pk=self.status_update.pk)
        self.assertEqual(self.status_update.url, 'https://example.com/build')
        self.assertEqual(self.status_update.state,
                         StatusUpdate.DONE_SUCCESS)

    def test_webhook_build_error(self):
        """Testing TravisCIWebHookView build error"""
        payload = json.dumps({
            'matrix': [
                {
                    'config': {
                        'env': [
                            'REVIEWBOARD_STATUS_UPDATE_ID=%d'
                            % self.status_update.pk,
                            'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d'
                            % self.config.pk,
                        ],
                    },
                },
            ],
            'build_url': 'https://example.com/build',
            'state': 'failed',
        })
        self.spy_on(TravisCIWebHookView._validate_signature,
                    owner=TravisCIWebHookView,
                    call_fake=lambda self, request, integration_config: True)

        rsp = self.client.post(self.webhook_url, {'payload': payload})

        self.assertEqual(rsp.status_code, 200)

        self.status_update = StatusUpdate.objects.get(pk=self.status_update.pk)
        self.assertEqual(self.status_update.url, 'https://example.com/build')
        self.assertEqual(self.status_update.state,
                         StatusUpdate.DONE_FAILURE)
