"""Unit tests for the Travis CI integration."""

from __future__ import unicode_literals

import json

from django.utils.six.moves.urllib.error import HTTPError
from djblets.conditions import ConditionSet, Condition
from reviewboard.hostingsvcs.models import HostingServiceAccount
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice

from rbintegrations.travisci.api import TravisAPI
from rbintegrations.travisci.forms import TravisCIIntegrationConfigForm
from rbintegrations.travisci.integration import TravisCIIntegration
from rbintegrations.testing.testcases import IntegrationTestCase


class TravisCIIntegrationTests(IntegrationTestCase):
    """Tests for Travis CI."""

    integration_cls = TravisCIIntegration
    fixtures = ['test_scmtools', 'test_users']

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

        self.spy_on(TravisAPI._make_request, call_fake=_make_request)

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
        self.assertTrue('git checkout %s' % diffset.base_commit_id
                        in data['request']['config']['script'])
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

        self.spy_on(TravisAPI._make_request, call_fake=_make_request)

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
                        in data['request']['config']['script'])
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

        self.spy_on(TravisAPI._make_request, call_original=False)

        review_request.publish(review_request.submitter)

        self.assertFalse(TravisAPI._make_request.called)

    def test_travisci_config_form_valid(self):
        """Testing TravisCIIntegrationConfigForm validation success"""
        form = TravisCIIntegrationConfigForm(
            self.integration,
            None,
            data={
                'conditions_last_id': 0,
                'conditions_mode': 'always',
                'name': 'test',
                'travis_endpoint': TravisAPI.OPEN_SOURCE_ENDPOINT,
                'travis_ci_token': '123456',
                'travis_yml': 'script:\n    - python ./tests/runtests.py',
            })

        self.spy_on(TravisAPI.get_user, call_original=False)
        self.spy_on(TravisAPI.lint,
                    call_fake=lambda x, travis_yml: {'warnings': []})

        self.assertTrue(form.is_valid())

    def test_travisci_config_form_lint_failure(self):
        """Testing TravisCIIntegrationConfigForm validation lint failure"""
        self.spy_on(TravisAPI.get_user, call_original=False)
        self.spy_on(
            TravisAPI.lint, call_fake=lambda x, travis_yml: {
                'warnings': [{
                    'key': 'script',
                    'message': 'An error',
                }],
            })

        form = TravisCIIntegrationConfigForm(
            self.integration,
            None,
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

        self.spy_on(TravisAPI.get_user, call_fake=_raise_403)

        form = TravisCIIntegrationConfigForm(
            self.integration,
            None,
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
                }), {}

            service = account.service
            self.spy_on(service.client.http_post,
                        call_fake=_http_post_authorize)

            service.authorize('myuser', 'mypass', None)
            self.assertTrue(account.is_authorized)

            service.client.http_post.unspy()

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
