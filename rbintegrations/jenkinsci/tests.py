"""Unit tests for the Jenkins CI integration."""

from __future__ import unicode_literals

import json

import kgb
import reviewboard
from django.utils.encoding import force_bytes
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
        review_request = self._setup_build_requests()
        review_request.publish(review_request.submitter)

        self._check_build_requests(payload={
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
                    'name': 'REVIEWBOARD_REVIEW_BRANCH',
                    'value': review_request.branch
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

    def test_build_new_review_request_with_local_site(self):
        """Testing JenkinsCIIntegration builds a new review request with a
        local site
        """
        review_request = self._setup_build_requests(with_local_site=True)
        review_request.publish(review_request.submitter)

        self._check_build_requests(payload={
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
                    'name': 'REVIEWBOARD_REVIEW_BRANCH',
                    'value': review_request.branch
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

    def test_manual_run_no_build_on_publish(self):
        """Testing lack of JenkinsCIIntegration build when a new review
        request is made with the run manually configuration
        """
        review_request = self._setup_build_requests(run_manually=True)
        review_request.publish(review_request.submitter)

        self._check_build_requests(expect_fetch_csrf_token=False,
                                   expect_open_request=False)

    def test_build_manual_run(self):
        """Testing JenkinsCIIntegration build via a manual trigger"""
        review_request = self._setup_build_requests(run_manually=True)

        status_update = \
            self.create_status_update(service_id='jenkins-ci',
                                      review_request=review_request)

        status_update_request_run.send(sender=self.__class__,
                                       status_update=status_update)

        self._check_build_requests(payload={
            'parameter': [
                {
                    'name': 'REVIEWBOARD_SERVER',
                    'value': 'http://example.com/',
                },
                {
                    'name': 'REVIEWBOARD_REVIEW_ID',
                    'value': review_request.display_id,
                },
                {
                    'name': 'REVIEWBOARD_REVIEW_BRANCH',
                    'value': review_request.branch
                },
                {
                    'name': 'REVIEWBOARD_DIFF_REVISION',
                    'value': 1,
                },
                {
                    'name': 'REVIEWBOARD_STATUS_UPDATE_ID',
                    'value': 1,
                }
            ]
        })

    def test_build_new_review_request_no_csrf_protection(self):
        """Testing that JenkinsCIIntegration builds a new review request
        without csrf protection
        """
        review_request = self._setup_build_requests(
            csrf_error=HTTPError('', 404, 'Not found', None, None))
        review_request.publish(review_request.submitter)

        self._check_build_requests(
            payload={
                'parameter': [
                    {
                        'name': 'REVIEWBOARD_SERVER',
                        'value': 'http://example.com/',
                    },
                    {
                        'name': 'REVIEWBOARD_REVIEW_ID',
                        'value': review_request.display_id,
                    },
                    {
                        'name': 'REVIEWBOARD_REVIEW_BRANCH',
                        'value': review_request.branch
                    },
                    {
                        'name': 'REVIEWBOARD_DIFF_REVISION',
                        'value': 1,
                    },
                    {
                        'name': 'REVIEWBOARD_STATUS_UPDATE_ID',
                        'value': 1,
                    }
                ],
            },
            expect_csrf_protection=False)

    def test_build_new_review_request_crumb_fetch_error(self):
        """Testing that JenkinsCIIntegration does not build when fetching the
        csrf token (or crumb) results in a non-404 error code
        """
        review_request = self._setup_build_requests(
            csrf_error=HTTPError('', 400, 'Bad request', None, None))
        review_request.publish(review_request.submitter)

        self._check_build_requests(expect_open_request=False)

    def test_job_name_variables_replaced(self):
        """Testing that JenkinsCIIntegration correctly replaces variables in a
        job name
        """
        review_request = self._setup_build_requests(
            job_name='{repository}_{branch}_1')
        review_request.publish(review_request.submitter)

        self._check_build_requests(
            url='http://localhost:8000/job/Test%20Repo_my-branch_1/build',
            payload={
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
                        'name': 'REVIEWBOARD_REVIEW_BRANCH',
                        'value': review_request.branch
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

    def _create_config(self, job_name=None, with_local_site=False,
                       run_manually=False):
        """Create an integration config.

        Args:
            job_name (string, optional):
                The Jenkins job name, which is used in constructing the
                URL to start a build on Jenkins.

            with_local_site (bool, optional):
                Whether to create the configuration for a Local Site.

            run_manually (bool, optional):
                Whether to run JenkinsCIIntegration manually.

        Returns:
            reviewboard.integrations.models.IntegrationConfig:
            The resulting integration configuration.
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
        config.set('jenkins_job_name', job_name or 'job_1')
        config.set('jenkins_endpoint', 'http://localhost:8000')
        config.set('jenkins_username', 'admin')
        config.set('jenkins_password', 'admin')
        config.set('run_manually', run_manually)
        config.save()

        return config

    def _setup_build_requests(self, with_local_site=False, run_manually=False,
                              job_name=None, csrf_error=None):
        """Set up state for build-related tests.

        This will set up a repository, review request, integration
        configuration, and spies for a build-related unit test.

        Args:
            with_local_site (bool, optional):
                Whether the tests should be performed against a Local Site.

            run_manually (bool, optional):
                Whether to create the integration configuration with
                ``run_manually`` set.

            job_name (unicode, optional):
                An explicit name or pattern to give the job.

            csrf_error (Exception, optional):
                An optional exception to raise for the CSRF request.

                If not provided, a successful payload will be returned
                instead.

        Returns:
            reviewboard.reviews.models.ReviewRequest:
            The created review request.
        """
        repository = self.create_repository(with_local_site=with_local_site)
        review_request = self.create_review_request(
            repository=repository,
            with_local_site=with_local_site)

        diffset = self.create_diffset(review_request=review_request)
        diffset.base_commit_id = '8fd69d70f07b57c21ad8733c1c04ae604d21493f'
        diffset.save(update_fields=('base_commit_id',))

        self._create_config(with_local_site=with_local_site,
                            run_manually=run_manually,
                            job_name=job_name)
        self.integration.enable_integration()

        # We'll always perform a CSRF check before any build request. This
        # code works under that assumption. Assertions later will confirm
        # them.
        def _handle_csrf(*args, **kwarga):
            if csrf_error:
                raise csrf_error

            return json.dumps({
                'crumb': 'crumb123',
                'crumbRequestField': 'crumbField',
            }).encode('utf-8')

        self.spy_on(
            JenkinsAPI._open_request,
            owner=JenkinsAPI,
            op=kgb.SpyOpMatchInOrder([
                {
                    'call_fake': _handle_csrf,
                },
                {
                    'call_fake': lambda *args, **kwargs: b'',
                },
            ]))

        return review_request

    def _check_build_requests(self,
                              url='http://localhost:8000/job/job_1/build',
                              payload=None,
                              expect_fetch_csrf_token=True,
                              expect_open_request=True,
                              expect_csrf_protection=True):
        """Check the requests made via the API.

        Args:
            url (unicode, optional):
                The expected URL.

                This will be ignored if ``expect_open_request`` is ``False``.

            payload (dict):
                The expected JSON payload.

                This will be ignored if ``expect_open_request`` is ``False``.

            expect_fetch_csrf_token (bool, optional):
                Whether to expect :py:meth:`rbintegrations.jenkinsci.api.
                JenkinsAPI._fetch_csrf_token` to be called.

            expect_open_request (bool, optional):
                Whether to expect :py:meth:`rbintegrations.jenkinsci.api.
                JenkinsAPI._open_request` to be called.

            expect_csrf_protection (bool, optional):
                Whether to expect that CSRF protection was enabled for
                build requests.

        Raises:
            AssertionError:
                One of the checks failed.
        """
        if expect_fetch_csrf_token and expect_open_request:
            self.assertSpyCallCount(JenkinsAPI._open_request, 2)
        elif expect_fetch_csrf_token or expect_open_request:
            self.assertSpyCallCount(JenkinsAPI._open_request, 1)
        else:
            self.assertSpyNotCalled(JenkinsAPI._open_request)

        call_index = 0

        # Check the CSRF call.
        if expect_fetch_csrf_token:
            self._check_http_request(
                call_index=call_index,
                url='http://localhost:8000/crumbIssuer/api/json')
            call_index += 1

        # Check the build request.
        if expect_open_request:
            if expect_csrf_protection:
                crumb = 'crumb123'
            else:
                crumb = None

            self._check_http_request(
                call_index=call_index,
                url=url,
                content_type='application/x-www-form-urlencoded',
                crumb=crumb,
                data=force_bytes(urlencode({
                    'json': json.dumps(payload, sort_keys=True),
                })))

    def _check_http_request(self, call_index, url, data=None,
                            content_type=None, crumb=None):
        """Check the contents of an HTTP request.

        This will ensure the request has the expected URL, payload, and
        headers.

        Args:
            call_index (int):
                The index of this particular HTTP call.

            url (unicode):
                The expected URL.

            data (bytes, optional):
                The expected request payload contents.

            content_type (unicode, optional):
                The expected value of the :mimeheader:`Content-type` header.

            crumb (unicode, optional):
                The expected value of the crumb header from a CSRF
                request.

        Raises:
            AssertionError:
                One of the checks failed.
        """
        request = JenkinsAPI._open_request.calls[call_index].args[0]

        if reviewboard.VERSION[0] >= 4:
            request_url = request.url
        else:
            request_url = request.get_full_url()

        self.assertEqual(request_url, url)
        self.assertEqual(request.data, data)
        self.assertEqual(request.headers.get('Content-type'), content_type)
        self.assertEqual(request.headers.get('Crumbfield'), crumb)
