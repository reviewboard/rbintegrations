"""Unit tests for the Travis CI integration."""

from __future__ import unicode_literals

import json

from django.core.urlresolvers import reverse
from django.utils.six.moves.urllib.error import HTTPError
from djblets.conditions import ConditionSet, Condition
from reviewboard.hostingsvcs.models import HostingServiceAccount
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice
from reviewboard.reviews.models import StatusUpdate

from rbintegrations.travisci.api import TravisAPI
from rbintegrations.travisci.forms import TravisCIIntegrationConfigForm
from rbintegrations.travisci.integration import TravisCIIntegration
from rbintegrations.travisci.views import TravisCIWebHookView
from rbintegrations.testing.testcases import IntegrationTestCase

try:
    # Review Board >= 4.0
    from reviewboard.hostingsvcs.service import (HostingServiceHTTPRequest,
                                                 HostingServiceHTTPResponse)
except ImportError:
    # Review Board < 4.0
    HostingServiceHTTPRequest = None
    HostingServiceHTTPResponse = None


class BaseTravisCITestCase(IntegrationTestCase):
    """Base class for Travis CI tests."""

    integration_cls = TravisCIIntegration
    fixtures = ['test_scmtools', 'test_users']

    def _create_repository(self, github=True):
        """Create and return a repository for testing.

        Args:
            github (bool, optional):
                Whether the repository should use the GitHub hosting service.

        Returns:
            reviewboard.scmtools.models.Repository:
            A repository for use in unit tests.
        """
        if github:
            account = HostingServiceAccount(service_name='github',
                                            username='myuser')

            # Review Board <= 3.0.17.
            def _http_post_authorize(self, *args, **kwargs):
                return json.dumps({
                    'id': 1,
                    'url': 'https://api.github.com/authorizations/1',
                    'scopes': ['user', 'repo'],
                    'token': 'abc123',
                    'note': '',
                    'note_url': '',
                    'updated_at': '2012-05-04T03:30:00Z',
                    'created_at': '2012-05-04T03:30:00Z',
                }).encode('utf-8'), {}

            # Review Board >= 3.0.18.
            def _http_get_user(_self, url, *args, **kwargs):
                self.assertEqual(url, 'https://api.github.com/user')

                payload = b'{}'
                headers = {
                    str('X-OAuth-Scopes'): str('admin:repo_hook, repo, user'),
                }

                if HostingServiceHTTPResponse is not None:
                    # Review Board >= 4.0
                    return HostingServiceHTTPResponse(
                        request=HostingServiceHTTPRequest(url=url),
                        url=url,
                        data=payload,
                        headers=headers,
                        status_code=200)
                else:
                    # Review Board < 4.0
                    return payload, headers

            service = account.service
            self.spy_on(service.client.http_post,
                        call_fake=_http_post_authorize)
            self.spy_on(service.client.http_get,
                        call_fake=_http_get_user)

            service.authorize('myuser', 'mypass', None)
            self.assertTrue(account.is_authorized)

            service.client.http_post.unspy()
            service.client.http_get.unspy()

            repository = self.create_repository()
            repository.hosting_account = account
            repository.extra_data['repository_plan'] = 'public-org'
            repository.extra_data['github_public_org_name'] = 'myorg'
            repository.extra_data['github_public_org_repo_name'] = 'myrepo'
            repository.save()
            return repository
        else:
            return self.create_repository()

    def _create_config(self, enterprise=False, with_local_site=False):
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

        if enterprise:
            config.set('travis_endpoint', TravisAPI.ENTERPRISE_ENDPOINT)
            config.set('travis_custom_endpoint', 'https://travis.example.com/')
        else:
            config.set('travis_endpoint', TravisAPI.OPEN_SOURCE_ENDPOINT)

        config.save()

        return config


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

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://api.travis-ci.org/repo/myorg%2Fmyrepo/requests')

        self.assertEqual(
            data['request']['config']['env']['global'],
            [
                'REVIEWBOARD_STATUS_UPDATE_ID=1',
                'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d' % config.pk,
            ])

        self.assertEqual(data['request']['message'],
                         'Test Summary\n\nTest Description')
        self.assertTrue('git fetch --unshallow origin'
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

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://travis.example.com/api/repo/myorg%2Fmyrepo/requests')

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

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://travis.example.com/api/repo/myorg%2Fmyrepo/requests')

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

        review_request.publish(review_request.submitter)

        self.assertTrue(TravisAPI._make_request.called)

        self.assertEqual(
            data['url'],
            'https://api.travis-ci.org/repo/myorg%2Fmyrepo/requests')

        self.assertEqual(
            data['request']['config']['env']['global'],
            [
                'REVIEWBOARD_STATUS_UPDATE_ID=1',
                'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d' % config.pk,
            ])
        self.assertEqual(data['request']['message'],
                         'Test Summary\n\nTest Description')
        self.assertFalse('git fetch --unshallow origin'
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
