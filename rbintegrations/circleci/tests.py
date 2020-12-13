"""Unit tests for the CircleCI integration."""

from __future__ import unicode_literals

import json

from django.utils.six.moves.urllib.request import urlopen
from djblets.conditions import ConditionSet, Condition
from reviewboard.hostingsvcs.models import HostingServiceAccount
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice

from rbintegrations.circleci.integration import CircleCIIntegration
from rbintegrations.testing.testcases import IntegrationTestCase

try:
    # Review Board >= 4.0
    from reviewboard.hostingsvcs.service import (HostingServiceHTTPRequest,
                                                 HostingServiceHTTPResponse)
except ImportError:
    # Review Board < 4.0
    HostingServiceHTTPRequest = None
    HostingServiceHTTPResponse = None


class CircleCIIntegrationTests(IntegrationTestCase):
    """Tests for CircleCI."""

    integration_cls = CircleCIIntegration
    fixtures = ['test_scmtools', 'test_site', 'test_users']

    def test_build_new_review_request(self):
        """Testing CircleCIIntegration builds a new review request"""
        repository = self._create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        data = self._spy_on_urlopen()

        review_request.publish(review_request.submitter)

        self.assertTrue(urlopen.spy.called)
        self.assertEqual(data['url'],
                         'https://circleci.com/api/v1.1/project/github/'
                         'mypublicorg/mypublicorgrepo/tree/review-requests?'
                         'circle-token=None')

        self.assertEqual(data['build_params']['CIRCLE_JOB'], 'reviewboard')
        self.assertIn('REVIEWBOARD_API_TOKEN', data['build_params'])
        self.assertIn('REVIEWBOARD_DIFF_REVISION', data['build_params'])
        self.assertIn('REVIEWBOARD_REVIEW_REQUEST', data['build_params'])
        self.assertIn('REVIEWBOARD_SERVER', data['build_params'])
        self.assertIn('REVIEWBOARD_STATUS_UPDATE_ID', data['build_params'])

    def test_build_new_review_request_with_local_site(self):
        """Testing CircleCIIntegration builds a new review request with a local
        site"""
        repository = self._create_repository(with_local_site=True)
        review_request = self.create_review_request(repository=repository,
                                                    with_local_site=True)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        data = self._spy_on_urlopen()

        review_request.publish(review_request.submitter)

        self.assertTrue(urlopen.spy.called)
        self.assertEqual(data['url'],
                         'https://circleci.com/api/v1.1/project/github/'
                         'mypublicorg/mypublicorgrepo/tree/review-requests?'
                         'circle-token=None')

        self.assertEqual(data['build_params']['CIRCLE_JOB'], 'reviewboard')
        self.assertIn('REVIEWBOARD_API_TOKEN', data['build_params'])
        self.assertIn('REVIEWBOARD_DIFF_REVISION', data['build_params'])
        self.assertIn('REVIEWBOARD_REVIEW_REQUEST', data['build_params'])
        self.assertIn('REVIEWBOARD_STATUS_UPDATE_ID', data['build_params'])

        self.assertEqual(data['build_params']['REVIEWBOARD_SERVER'],
                         'http://example.com/s/%s/' % self.local_site_name)
        self.assertEqual(data['build_params']['REVIEWBOARD_LOCAL_SITE'],
                         self.local_site_name)

    def test_non_github_review_request(self):
        """Testing CircleCIIntegration skipping a non-GitHub review request"""
        repository = self._create_repository(github=False)
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)

        review_request.publish(review_request.submitter)

        self.assertFalse(urlopen.spy.called)

    def test_build_new_review_request_with_public_github_repository(self):
        """Testing CircleCIIntegration builds for a new review request with
        a public GitHub repository"""
        repository = self._create_repository(github=True,
                                             repository_plan='public')
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        data = self._spy_on_urlopen()

        review_request.publish(review_request.submitter)

        self.assertTrue(urlopen.spy.called)
        self.assertEqual(data['url'],
                         'https://circleci.com/api/v1.1/project/github/'
                         'myuser/mypublicrepo/tree/review-requests?'
                         'circle-token=None')

    def test_build_new_review_request_with_private_github_repository(self):
        """Testing CircleCIIntegration builds for a new review request with
        a private GitHub repository"""
        repository = self._create_repository(github=True,
                                             repository_plan='private')
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        data = self._spy_on_urlopen()

        review_request.publish(review_request.submitter)

        self.assertTrue(urlopen.spy.called)
        self.assertEqual(data['url'],
                         'https://circleci.com/api/v1.1/project/github/'
                         'myuser/myprivaterepo/tree/review-requests?'
                         'circle-token=None')

    def test_build_new_review_request_with_private_org_github_repository(self):
        """Testing CircleCIIntegration builds for a new review request with
        a private organization GitHub repository"""
        repository = self._create_repository(github=True,
                                             repository_plan='private-org')
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        data = self._spy_on_urlopen()

        review_request.publish(review_request.submitter)

        self.assertTrue(urlopen.spy.called)
        self.assertEqual(data['url'],
                         'https://circleci.com/api/v1.1/project/github/'
                         'myprivateorg/myprivateorgrepo/tree/review-requests?'
                         'circle-token=None')

    def _create_repository(self,
                           github=True,
                           with_local_site=False,
                           repository_plan='public-org'):
        """Create and return a repository for testing.

        Args:
            github (bool, optional):
                Whether the repository should use the GitHub hosting service.

            with_local_site (bool, optional):
                Whether to limit the config to a local site.

            repository_plan (unicode, optional):
                The type of GitHub repository plan.

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

            repository = self.create_repository(
                with_local_site=with_local_site)
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

    def _create_config(self, with_local_site=False):
        """Create an integration config.

        Args:
            with_local_site (bool):
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
        config.set('branch_name', 'review-requests')
        config.save()

        return config

    def _spy_on_urlopen(self):
        """Wrapper function for spying on the urlopen function.

        Returns:
            dict:
            Faked response from CircleCI.
        """
        data = {}

        def _urlopen(request, **kwargs):
            # We can't actually do any assertions in here, because they'll get
            # swallowed by SignalHook's sandboxing. We therefore record the
            # data we need and assert later.
            data['url'] = request.get_full_url()
            data['build_params'] = json.loads(request.data)['build_parameters']

            class _Response(object):
                def read(self):
                    return json.dumps({
                        'build_url': 'http://example.com/gh/org/project/35',
                    })

            return _Response()

        self.spy_on(urlopen, call_fake=_urlopen)

        return data
