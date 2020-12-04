"""Unit tests for the Jenkins CI integration."""

from __future__ import unicode_literals

import json

from django.utils.six.moves.urllib.error import HTTPError
from django.utils.six.moves.urllib.parse import urlencode
from djblets.conditions import ConditionSet, Condition
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice
from reviewboard.reviews.signals import status_update_request_run

from rbintegrations.jenkinsci.api import JenkinsAPI
from rbintegrations.jenkinsci.integration import JenkinsCIIntegration
from rbintegrations.testing.testcases import IntegrationTestCase


class JenkinsCIIntegrationTests(IntegrationTestCase):
    """Tests for Jenkins CI."""

    integration_cls = JenkinsCIIntegration
    fixtures = ['test_scmtools', 'test_site', 'test_users']

    def test_build_new_review_request(self):
        """Testing JenkinsCIIntegration builds a new review request"""
        repository = self.create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        data = self._spy_on_make_raw_request()
        self.spy_on(JenkinsAPI._fetch_csrf_token,
                    owner=JenkinsAPI,
                    call_original=False)

        review_request.publish(review_request.submitter)

        self.assertEqual(data['url'], 'http://localhost:8000/job/job_1/build')

        self.assertEqual(data['request'], urlencode({
            'json': json.dumps({
                'parameter': [
                    {
                        'name': 'REVIEWBOARD_SERVER',
                        'value': 'http://example.com/'
                    },
                    {
                        'name': 'REVIEWBOARD_REVIEW_ID',
                        'value': review_request.display_id
                    },
                    {
                        'name': 'REVIEWBOARD_DIFF_REVISION',
                        'value': 1
                    },
                    {
                        'name': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': 1
                    }
                ]
            })
        }))

        self.assertTrue(JenkinsAPI._make_raw_request.called)
        self.assertTrue(JenkinsAPI._fetch_csrf_token.called)

    def test_build_new_review_request_with_local_site(self):
        """Testing JenkinsCIIntegration builds a new review request with a
        local site"""
        repository = self.create_repository(with_local_site=True)
        review_request = self.create_review_request(repository=repository,
                                                    with_local_site=True)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        data = self._spy_on_make_raw_request()
        self.spy_on(JenkinsAPI._fetch_csrf_token,
                    owner=JenkinsAPI,
                    call_original=False)

        review_request.publish(review_request.submitter)

        self.assertEqual(data['url'], 'http://localhost:8000/job/job_1/build')

        self.assertEqual(data['request'], urlencode({
            'json': json.dumps({
                'parameter': [
                    {
                        'name': 'REVIEWBOARD_SERVER',
                        'value': ('http://example.com/s/%s/' %
                                  self.local_site_name)
                    },
                    {
                        'name': 'REVIEWBOARD_REVIEW_ID',
                        'value': review_request.display_id
                    },
                    {
                        'name': 'REVIEWBOARD_DIFF_REVISION',
                        'value': 1
                    },
                    {
                        'name': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': 1
                    }
                ]
            })
        }))

        self.assertTrue(JenkinsAPI._make_raw_request.called)
        self.assertTrue(JenkinsAPI._fetch_csrf_token.called)

    def test_manual_run_no_build_on_publish(self):
        """Testing lack of JenkinsCIIntegration build when a new review
        request is made with the run manually configuration"""
        repository = self.create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config(run_manually=True)
        self.integration.enable_integration()

        data = self._spy_on_make_raw_request()
        self.spy_on(JenkinsAPI._fetch_csrf_token,
                    owner=JenkinsAPI,
                    call_original=False)

        review_request.publish(review_request.submitter)

        self.assertEqual(data, {})

        self.assertFalse(JenkinsAPI._make_raw_request.called)
        self.assertFalse(JenkinsAPI._fetch_csrf_token.called)

    def test_build_manual_run(self):
        """Testing JenkinsCIIntegration build via a manual trigger"""
        repository = self.create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config(run_manually=True)
        self.integration.enable_integration()

        status_update = \
            self.create_status_update(service_id='jenkins-ci',
                                      review_request=review_request)

        data = self._spy_on_make_raw_request()
        self.spy_on(JenkinsAPI._fetch_csrf_token,
                    owner=JenkinsAPI,
                    call_original=False)

        status_update_request_run.send(sender=self.__class__,
                                       status_update=status_update)

        self.assertEqual(data['url'], 'http://localhost:8000/job/job_1/build')

        self.assertEqual(data['request'], urlencode({
            'json': json.dumps({
                'parameter': [
                    {
                        'name': 'REVIEWBOARD_SERVER',
                        'value': 'http://example.com/'
                    },
                    {
                        'name': 'REVIEWBOARD_REVIEW_ID',
                        'value': review_request.display_id
                    },
                    {
                        'name': 'REVIEWBOARD_DIFF_REVISION',
                        'value': 1
                    },
                    {
                        'name': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': 1
                    }
                ]
            })
        }))

        self.assertTrue(JenkinsAPI._make_raw_request.called)
        self.assertTrue(JenkinsAPI._fetch_csrf_token.called)

    def test_build_new_review_request_no_csrf_protection(self):
        """Testing that JenkinsCIIntegration builds a new review request
        without csrf protection"""
        repository = self.create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        def _fetch_csrf_token(api):
            raise HTTPError('', 404, 'Not found', None, None)

        self.spy_on(JenkinsAPI._make_raw_request,
                    owner=JenkinsAPI,
                    call_original=False)
        self.spy_on(JenkinsAPI._fetch_csrf_token,
                    call_fake=_fetch_csrf_token,
                    owner=JenkinsAPI)

        review_request.publish(review_request.submitter)

        self.assertTrue(JenkinsAPI._make_raw_request.called)

    def test_build_new_review_request_crumb_fetch_error(self):
        """Testing that JenkinsCIIntegration does not build when fetching the
        csrf token (or crumb) results in a non-404 error code"""
        repository = self.create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config()
        self.integration.enable_integration()

        def _fetch_csrf_token(api):
            raise HTTPError('', 400, 'Bad request', None, None)

        self.spy_on(JenkinsAPI._make_raw_request,
                    owner=JenkinsAPI,
                    call_original=False)
        self.spy_on(JenkinsAPI._fetch_csrf_token,
                    owner=JenkinsAPI,
                    call_fake=_fetch_csrf_token)

        review_request.publish(review_request.submitter)

        self.assertFalse(JenkinsAPI._make_raw_request.called)

    def test_job_name_variables_replaced(self):
        """Testing that JenkinsCIIntegration correctly replaces variables in a
        job name"""
        repository = self.create_repository()
        review_request = self.create_review_request(repository=repository)
        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save()

        self._create_config(job_name='{repository}_{branch}_1')
        self.integration.enable_integration()

        data = self._spy_on_make_raw_request()
        self.spy_on(JenkinsAPI._fetch_csrf_token,
                    owner=JenkinsAPI,
                    call_original=False)

        review_request.publish(review_request.submitter)

        self.assertEqual(
            data['url'],
            'http://localhost:8000/job/Test%20Repo_my-branch_1/build')

    def _create_config(self, job_name='job_1', with_local_site=False,
                       run_manually=False):
        """Create an integration config.

        Args:
            job_name (string, optional):
                The Jenkins job name, which is used in constructing the
                URL to start a build on Jenkins.

            run_manually (bool, optional):
                Whether to run JenkinsCIIntegration manually.
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
        config.set('jenkins_job_name', job_name)
        config.set('jenkins_endpoint', 'http://localhost:8000')
        config.set('jenkins_username', 'admin')
        config.set('jenkins_password', 'admin')
        config.set('run_manually', run_manually)

        config.save()

        return config

    def _spy_on_make_raw_request(self):
        """Wrapper function for spying on the _make_raw_request function.

        Returns:
            dict:
            Faked response from Jenkins.
        """

        data = {}

        def _make_raw_request(api, url, body=None, method='GET', headers={},
                              content_type=None):
            # We can't actually do any assertions in here, because they'll get
            # swallowed by SignalHook's sandboxing. We therefore record the
            # data we need and assert later.
            data['url'] = url
            data['request'] = body
            return '{}'

        self.spy_on(JenkinsAPI._make_raw_request,
                    owner=JenkinsAPI,
                    call_fake=_make_raw_request)

        return data
