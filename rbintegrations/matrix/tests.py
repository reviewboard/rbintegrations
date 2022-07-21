"""Unit tests for Matrix"""

import json
from urllib.request import urlopen

from django.contrib.auth.models import User
from djblets.conditions import ConditionSet, Condition
from djblets.testing.decorators import add_fixtures
from reviewboard.accounts.trophies import TrophyType, trophies_registry
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice
from reviewboard.reviews.models import ReviewRequestDraft

from rbintegrations.matrix.integration import MatrixIntegration
from rbintegrations.testing.testcases import IntegrationTestCase


class MatrixIntegrationTests(IntegrationTestCase):
    """Tests for Matrix."""

    integration_cls = MatrixIntegration

    fixtures = ['test_scmtools', 'test_users']

    def setUp(self):
        super(MatrixIntegrationTests, self).setUp()

        self.user = User.objects.create(username='test',
                                        first_name='Test',
                                        last_name='User')

    def test_notify_new_review_request(self):
        """Testing MatrixIntegration notifies on new review request"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=False)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.publish(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review request from Test User: '
                    'http://example.com/r/1/</strong><p>#1: Test Review '
                    'Request</p><strong><font '
                    'color="#efcc96">Description</font></strong><p>My '
                    'description.</p><strong><font '
                    'color="#efcc96">Repository</font></strong><p>Test '
                    'Repo</p><strong><font '
                    'color="#efcc96">Branch</font></strong><p>my-branch</p>',
                'format': 'org.matrix.custom.html'
            })

    @add_fixtures(['test_site'])
    def test_notify_new_review_request_with_local_site(self):
        """Testing MatrixIntegration notifies on new review request with
        local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            publish=False)

        review_request.local_site.users.add(self.user)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.publish(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review request from Test User: '
                    'http://example.com/s/local-site-1/r/1/</strong><p>#1: '
                    'Test Review Request</p><strong><font color="#efcc96">'
                    'Description</font></strong><p>My '
                    'description.</p><strong><font color="#efcc96">'
                    'Repository</font></strong><p>Test Repo</p><strong><font '
                    'color="#efcc96">Branch</font></strong><p>my-branch</p>',
                'format': 'org.matrix.custom.html',
            })

    def test_notify_new_review_request_with_diff(self):
        """Testing MatrixIntegration notifies on new review request with diff
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=False)
        self.create_diffset(review_request)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.publish(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review request from Test User: '
                    'http://example.com/r/1/</strong><p>#1: '
                    'Test Review Request</p><strong><font '
                    'color="#efcc96">Description</font></strong><p>My'
                    ' description.</p><strong><font '
                    'color="#efcc96">Diff</font></strong><p>http:'
                    '//example.com/r/1/diff/1/ | Revision '
                    '1</p><strong><font color="#efcc96">Repository'
                    '</font></strong><p>Test '
                    'Repo</p><strong><font color="#efcc96">Branch'
                    '</font></strong><p>my-branch</p>',
                'format': 'org.matrix.custom.html'
            })

    @add_fixtures(['test_site'])
    def test_notify_new_review_request_with_local_site_and_diff(self):
        """Testing MatrixIntegration notifies on new review request with local
        site and diff
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            publish=False)

        self.create_diffset(review_request)

        review_request.local_site.users.add(self.user)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.publish(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review request from Test User: '
                    'http://example.com/s/local-site-1/r/1/</strong>'
                    '<p>#1: Test Review Request</p><strong><font '
                    'color="#efcc96">Description</font></strong><p>My'
                    ' description.</p><strong><font '
                    'color="#efcc96">Diff</font></strong><p>'
                    'http://example.com/s/local-site-1/r/1/diff/1/ | Revision '
                    '1</p><strong><font color="#efcc96">Repository</font>'
                    '</strong><p>Test Repo</p><strong><font '
                    'color="#efcc96">Branch</font></strong><p>my-branch</p>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_new_review_request_with_fish_trophy(self):
        """Testing MatrixIntegration notifies on new review request with
        fish trophy
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=False)
        review_request.id = 12321
        review_request.save()

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.publish(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#12321: New review request from Test User: '
                    'http://example.com/r/12321/</strong>'
                    '<p>#12321: Test Review Request</p><strong><font '
                    'color="#efcc96">Description</font></strong>'
                    '<p>My description.</p><strong><font '
                    'color="#efcc96">Repository</font></strong>'
                    '<p>Test Repo</p><strong><font '
                    'color="#efcc96">Branch</font></strong>'
                    '<p>my-branch</p>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_new_review_request_with_milestone_trophy(self):
        """Testing MatrixIntegration notifies on new review request with
        milestone trophy
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            id=10000,
            publish=False)

        review_request.save()

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.publish(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body': (
                    '<strong>#10000: New review request from Test User: '
                    'http://example.com/r/10000/</strong><p>#10000: Test '
                    'Review Request</p><strong><font color="#efcc96">'
                    'Description</font></strong><p>My description.</p>'
                    '<strong><font color="#efcc96">Repository</font></strong>'
                    '<p>Test Repo</p><strong><font color="#efcc96">'
                    'Branch</font></strong><p>my-branch</p>'
                ),
                'format': 'org.matrix.custom.html',
            })

    def test_notify_new_review_request_with_custom_trophy(self):
        """Testing MatrixIntegration notifies on new review request with
        ignored custom trophy
        """
        class MyTrophy(TrophyType):
            category = 'test'

            def __init__(self):
                super(MyTrophy, self).__init__(title='My Trophy',
                                               image_url='blahblah')

            def qualifies(self, review_request):
                return True

        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=False)
        review_request.save()

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)

        trophies_registry.register(MyTrophy)

        try:
            review_request.publish(self.user)
        finally:
            trophies_registry.unregister(MyTrophy)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review request from Test '
                    'User: http://example.com/r/1/</strong><p>#1: '
                    'Test Review Request</p><strong><font color="#efcc96">'
                    'Description</font></strong><p>My '
                    'description.</p><strong><font color="#efcc96">'
                    'Repository</font></strong><p>Test '
                    'Repo</p><strong><font color="#efcc96">Branch</font>'
                    '</strong><p>my-branch</p>',
                'format': 'org.matrix.custom.html'
            }
        )

    def test_notify_updated_review_request(self):
        """Testing MatrixIntegration notifies on updated review request"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=True)

        draft = ReviewRequestDraft.create(review_request)
        draft.summary = 'My new summary'
        draft.description = 'My new description'
        draft.save()

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.publish(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New update from Test User: '
                    'http://example.com/r/1/</strong><p>#1: My new '
                    'summary</p><strong><font color="#efcc96">'
                    'Repository</font></strong><p>Test '
                    'Repo</p><strong><font color="#efcc96">'
                    'Branch</font></strong><p>my-branch</p>',
                'format': 'org.matrix.custom.html'
            }
        )

    def test_notify_updated_review_request_with_change_description(self):
        """Testing MatrixIntegration notifies on updated review request with
        change description
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=True)

        draft = ReviewRequestDraft.create(review_request)
        draft.summary = 'My new summary'
        draft.description = 'My new description'
        draft.save()

        changedesc = draft.changedesc
        changedesc.text = 'These are my changes.'
        changedesc.save()

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.publish(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New update from Test User: '
                    'http://example.com/r/1/</strong><p>#1: My new '
                    'summary</p><strong><font color="#efcc96">'
                    'Repository</font></strong><p>Test '
                    'Repo</p><strong><font '
                    'color="#efcc96">Branch</font></strong><p>'
                    'my-branch</p><blockquote>These are my '
                    'changes.</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_closed_review_request_as_submitted(self):
        """Testing MatrixIntegration notifies on closing review request as
        submitted
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=True)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.close(review_request.SUBMITTED)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: Closed as completed by '
                    'Test User: http://example.com/r/1/</strong><p>#1: '
                    'Test Review Request</p>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_closed_review_request_as_discarded(self):
        """Testing MatrixIntegration notifies on closing review request as
        discarded
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=True)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.close(review_request.DISCARDED)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: Discarded by Test User:'
                    ' http://example.com/r/1/</strong><p>#1: Test '
                    'Review Request</p>',
                'format': 'org.matrix.custom.html'
            })

    @add_fixtures(['test_site'])
    def test_notify_closed_review_request_with_local_site(self):
        """Testing MatrixIntegration notifies on closing review request with
        local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            publish=True)

        review_request.local_site.users.add(self.user)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.close(review_request.SUBMITTED)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: Closed as completed by Test User: '
                    'http://example.com/s/local-site-1/r/1/'
                    '</strong><p>#1: Test Review Request</p>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_reopened_review_request(self):
        """Testing MatrixIntegration notifies on reopened review request"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=True)
        review_request.close(review_request.SUBMITTED)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.reopen(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: Reopened by Test User: '
                    'http://example.com/r/1/</strong><p>#1: Test Review '
                    'Request</p><blockquote>My description.</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    @add_fixtures(['test_site'])
    def test_notify_reopened_review_request_with_local_site(self):
        """Testing MatrixIntegration notifies on reopened review request with
        local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            publish=True)
        review_request.close(review_request.SUBMITTED)

        review_request.local_site.users.add(self.user)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review_request.reopen(self.user)

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: Reopened by Test User: '
                    'http://example.com/s/local-site-1/r/1/'
                    '</strong><p>#1: Test Review '
                    'Request</p><blockquote>My description.</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_new_review_with_body_top(self):
        """Testing MatrixIntegration notifies on new review with body_top"""
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    body_top='This is my review.')
        self.create_general_comment(review)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review from Test User: '
                    'http://example.com/r/1/#review1</strong><p>#1: '
                    'Test Review Request</p><blockquote>'
                    'This is my review.</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    @add_fixtures(['test_site'])
    def test_notify_new_review_with_local_site(self):
        """Testing MatrixIntegration notifies on new review with local site"""
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)

        review_request.local_site.users.add(self.user)

        review = self.create_review(review_request,
                                    user=self.user,
                                    body_top='This is my review.')
        self.create_general_comment(review)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review from Test User: '
                    'http://example.com/s/local-site'
                    '-1/r/1/#review1</strong><p>#1: Test Review '
                    'Request</p><blockquote>This is '
                    'my review.</blockquote>',
                'format': 'org.matrix.custom.html'
            }
        )

    def test_notify_new_review_with_comments(self):
        """Testing MatrixIntegration notifies on new review with only comments
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request, user=self.user,
                                    body_top='')
        self.create_general_comment(review, text='My general comment.')

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review from Test User: '
                    'http://example.com/r/1/#review1</strong><p>#1: '
                    'Test Review Request</p><blockquote>My '
                    'general comment.</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_new_review_with_one_open_issue(self):
        """Testing MatrixIntegration notifies on new review with 1 open
        issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request, user=self.user,
                                    body_top='')
        self.create_general_comment(review, text='My general comment.',
                                    issue_opened=True)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review from Test User (1 issue): '
                    'http://example.com/r/1/#review1</strong>'
                    '<p>#1: Test Review Request</p><strong><font '
                    'color="warning">Open Issues</font></strong>'
                    '<p>⚠ 1 issue</p><blockquote>My general '
                    'comment.</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_new_review_with_open_issues(self):
        """Testing MatrixIntegration notifies on new review with > 1 open
        issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request, user=self.user,
                                    body_top='')
        self.create_general_comment(review, text='My general comment.',
                                    issue_opened=True)
        self.create_general_comment(review, text='My general comment 2.',
                                    issue_opened=True)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review from Test User (2 issues): '
                    'http://example.com/r/1/#review1</strong>'
                    '<p>#1: Test Review Request</p><strong><font '
                    'color="warning">Open Issues</font></strong>'
                    '<p>⚠ 2 issues</p><blockquote>My general '
                    'comment.</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_new_review_with_ship_it(self):
        """Testing MatrixIntegration notifies on new review with Ship It!"""
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True,
                                    body_top='Ship It!')
        self.create_general_comment(review)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review from Test User (Ship it!): '
                    'http://example.com/r/1/#review1</strong><p>'
                    '#1: Test Review Request</p><strong><font '
                    'color="good">Ship it!</font></strong>'
                    '<p>✅</p>',
                'format': 'org.matrix.custom.html'
            }
        )

    def test_notify_new_review_with_ship_it_and_custom_body_top(self):
        """Testing MatrixIntegration notifies on new review with Ship It and
        custom body_top
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True,
                                    body_top='This is body_top.')
        self.create_general_comment(review)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review from Test User (Ship it!): '
                    'http://example.com/r/1/#review1'
                    '</strong><p>#1: Test Review Request</p><strong><font '
                    'color="good">Ship it!</font>'
                    '</strong><p>✅</p><blockquote>This is '
                    'body_top.</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_new_review_with_ship_it_and_one_open_issue(self):
        """Testing MatrixIntegration notifies on new review with Ship It! and
        1 open issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True,
                                    body_top='Ship It!')
        self.create_general_comment(review, issue_opened=True)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review from Test '
                    'User (Fix it, then Ship it!): '
                    'http://example.com/r/1/#review1'
                    '</strong><p>#1: Test Review Request</p><strong><font '
                    'color="warning">Fix it, then Ship it!'
                    '</font></strong><p>⚠ 1 issue</p>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_new_review_with_ship_it_and_open_issues(self):
        """Testing MatrixIntegration notifies on new review with Ship It! and
        > 1 open issues
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True,
                                    body_top='Ship It!')
        self.create_general_comment(review, issue_opened=True)
        self.create_general_comment(review, issue_opened=True)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        review.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New review from Test '
                    'User (Fix it, then Ship it!): '
                    'http://example.com/r/1/#review1'
                    '</strong>'
                    '<p>#1: Test Review '
                    'Request</p><strong><font '
                    'color="warning">Fix it, then Ship '
                    'it!</font></strong><p>⚠ 2 issues</p>',
                'format': 'org.matrix.custom.html'
            }
        )

    def test_notify_new_reply_with_body_top(self):
        """Testing MatrixIntegration notifies on new reply with body_top"""
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    publish=True)
        comment = self.create_general_comment(review, issue_opened=True)

        reply = self.create_reply(review,
                                  user=self.user,
                                  body_top='This is body_top.')
        self.create_general_comment(reply,
                                    text='This is a comment.',
                                    reply_to=comment)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        reply.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New reply from Test User: '
                    'http://example.com/r/1/#review2</strong><p>#1: '
                    'Test Review '
                    'Request</p><blockquote>This is body_top.'
                    '</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    @add_fixtures(['test_site'])
    def test_notify_new_reply_with_local_site(self):
        """Testing MatrixIntegration notifies on new reply with local site"""
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)

        review_request.local_site.users.add(self.user)

        review = self.create_review(review_request,
                                    user=self.user,
                                    publish=True)
        comment = self.create_general_comment(review, issue_opened=True)

        reply = self.create_reply(review,
                                  user=self.user,
                                  body_top='This is body_top.')
        self.create_general_comment(reply,
                                    text='This is a comment.',
                                    reply_to=comment)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        reply.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New reply from Test User: '
                    'http://example.com/s/local-site-1/r/1/#review2'
                    '</strong><p>#1: Test Review '
                    'Request</p><blockquote>This is body_top.'
                    '</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    def test_notify_new_reply_with_comment(self):
        """Testing MatrixIntegration notifies on new reply with comment"""
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    publish=True)
        comment = self.create_general_comment(review, issue_opened=True)

        reply = self.create_reply(review, user=self.user, body_top='')
        self.create_general_comment(reply,
                                    text='This is a comment.',
                                    reply_to=comment)

        self._create_config()
        self.integration.enable_integration()

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)
        reply.publish()

        self.assertEqual(len(self.integration.notify.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'body': '',
                'msgtype': 'm.text',
                'formatted_body':
                    '<strong>#1: New reply from Test User: '
                    'http://example.com/r/1/#review2</strong><p>#1: '
                    'Test Review Request</p><blockquote>This '
                    'is a comment.</blockquote>',
                'format': 'org.matrix.custom.html'
            })

    def _create_config(self, with_local_site=False):
        """Create an integration config.

        Args:
            with_local_site (bool, optional):
                Whether to limit the config to a local site.

        Returns:
            reviewboard.integrations.models.IntegrationConfig:
            A config for Matrix Integration to be used for testing.
        """
        choice = ReviewRequestRepositoriesChoice()

        condition_set = ConditionSet(conditions=[
            Condition(choice=choice,
                      operator=choice.get_operator('any')),
        ])

        if with_local_site:
            local_site = self.get_local_site(name=self.local_site_name)
        else:
            local_site = None

        config = self.integration.create_config(name='Config 1',
                                                enabled=True,
                                                local_site=local_site)
        config.set('notify_username', 'RB User')
        config.set('access_token', 'matrix-example-token')
        config.set('room_id', 'matrix-example-id')
        config.set('conditions', condition_set.serialize())
        config.set('server', 'https://matrix.org')
        config.save()

        return config
