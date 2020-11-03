"""Tests for Mattermost"""
from __future__ import unicode_literals

import json

from django.contrib.auth.models import User
from django.utils.six.moves.urllib.request import urlopen
from djblets.conditions import ConditionSet, Condition
from djblets.testing.decorators import add_fixtures
from reviewboard.accounts.trophies import TrophyType, trophies_registry
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice
from reviewboard.reviews.models import ReviewRequestDraft

from rbintegrations.mattermost.integration import MattermostIntegration
from rbintegrations.testing.testcases import IntegrationTestCase


class MattermostIntegrationTests(IntegrationTestCase):
    """Tests Review Board integration with Mattermost."""

    integration_cls = MattermostIntegration
    fixtures = ['test_scmtools', 'test_users']

    def setUp(self):
        """Setting up MattermostIntegration for testing"""
        super(MattermostIntegrationTests, self).setUp()

        self.user = User.objects.create(username='test',
                                        first_name='Test',
                                        last_name='User')

    def test_notify_new_review_request(self):
        """Testing MattermostIntegration notifies on new review request"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New review request from Test User: '
                        'http://example.com/r/1/'
                    ),
                    'fields': [
                        {
                            'short': False,
                            'title': 'Description',
                            'value': 'My description.',
                        },
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/',
                    'text': None,
                    'pretext': (
                        'New review request from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    @add_fixtures(['test_site'])
    def test_notify_new_review_request_with_local_site(self):
        """Testing MattermostIntegration notifies on new review request with
        local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New review request from Test User: '
                        'http://example.com/s/local-site-1/r/1/'
                    ),
                    'fields': [
                        {
                            'short': False,
                            'title': 'Description',
                            'value': 'My description.',
                        },
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/s/local-site-1/r/1/',
                    'text': None,
                    'pretext': (
                        'New review request from '
                        '<http://example.com/s/local-site-1/users/test/'
                        '|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_request_with_diff(self):
        """Testing MattermostIntegration notifies on new review request with
        diff
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New review request from Test User: '
                        'http://example.com/r/1/'
                    ),
                    'fields': [
                        {
                            'short': False,
                            'title': 'Description',
                            'value': 'My description.',
                        },
                        {
                            'short': True,
                            'title': 'Diff',
                            'value': (
                                '<http://example.com/r/1/diff/1/|Revision 1>'
                            ),
                        },
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/',
                    'text': None,
                    'pretext': (
                        'New review request from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    @add_fixtures(['test_site'])
    def test_notify_new_review_request_with_local_site_and_diff(self):
        """Testing MattermostIntegration notifies on new review request with
        local site and diff
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New review request from Test User: '
                        'http://example.com/s/local-site-1/r/1/'
                    ),
                    'fields': [
                        {
                            'short': False,
                            'title': 'Description',
                            'value': 'My description.',
                        },
                        {
                            'short': True,
                            'title': 'Diff',
                            'value': (
                                '<http://example.com/s/local-site-1/r/1/'
                                'diff/1/|Revision 1>'
                            ),
                        },
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/s/local-site-1/r/1/',
                    'text': None,
                    'pretext': (
                        'New review request from '
                        '<http://example.com/s/local-site-1/users/test/'
                        '|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_request_with_image_file_attachment(self):
        """Testing MattermostIntegration notifies on new review request with
        image file attachment
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=False)
        attachment = self.create_file_attachment(review_request)

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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New review request from Test User: '
                        'http://example.com/r/1/'
                    ),
                    'fields': [
                        {
                            'short': False,
                            'title': 'Description',
                            'value': 'My description.',
                        },
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'image_url': attachment.get_absolute_url(),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/',
                    'text': None,
                    'pretext': (
                        'New review request from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_request_with_fish_trophy(self):
        """Testing MattermostIntegration notifies on new review request with
        fish trophy
        """
        review_request = self.create_review_request(
            create_repository=True,
            id=12321,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#12321: New review request from Test User: '
                        'http://example.com/r/12321/'
                    ),
                    'fields': [
                        {
                            'short': False,
                            'title': 'Description',
                            'value': 'My description.',
                        },
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'thumb_url': self.integration.TROPHY_URLS['fish'],
                    'title': '#12321: Test Review Request',
                    'title_link': 'http://example.com/r/12321/',
                    'text': None,
                    'pretext': (
                        'New review request from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_request_with_milestone_trophy(self):
        """Testing MattermostIntegration notifies on new review request with
        milestone trophy
        """
        review_request = self.create_review_request(
            create_repository=True,
            id=10000,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#10000: New review request from Test User: '
                        'http://example.com/r/10000/'
                    ),
                    'fields': [
                        {
                            'short': False,
                            'title': 'Description',
                            'value': 'My description.',
                        },
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'thumb_url': self.integration.TROPHY_URLS['milestone'],
                    'title': '#10000: Test Review Request',
                    'title_link': 'http://example.com/r/10000/',
                    'text': None,
                    'pretext': (
                        'New review request from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_request_with_custom_trophy(self):
        """Testing MattermostIntegration notifies on new review request with
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
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New review request from Test User: '
                        'http://example.com/r/1/'
                    ),
                    'fields': [
                        {
                            'short': False,
                            'title': 'Description',
                            'value': 'My description.',
                        },
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/',
                    'text': None,
                    'pretext': (
                        'New review request from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_updated_review_request(self):
        """Testing MattermostIntegration notifies on updated review request"""
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New update from Test User: '
                        'http://example.com/r/1/'
                    ),
                    'fields': [
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'title': '#1: My new summary',
                    'title_link': 'http://example.com/r/1/',
                    'text': '',
                    'pretext': (
                        'New update from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_updated_review_request_with_change_description(self):
        """Testing MattermostIntegration notifies on updated review request
        with change description
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New update from Test User: '
                        'http://example.com/r/1/'
                    ),
                    'fields': [
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'title': '#1: My new summary',
                    'title_link': 'http://example.com/r/1/',
                    'text': 'These are my changes.',
                    'pretext': (
                        'New update from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_updated_review_request_with_new_image_attachments(self):
        """Testing MattermostIntegration notifies on updated review request
        with new image attachments
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=False)
        self.create_file_attachment(review_request)
        review_request.publish(self.user)

        attachment = self.create_file_attachment(review_request,
                                                 caption='My new attachment',
                                                 draft=True)

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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New update from Test User: '
                        'http://example.com/r/1/'
                    ),
                    'fields': [
                        {
                            'short': True,
                            'title': 'Repository',
                            'value': 'Test Repo',
                        },
                        {
                            'short': True,
                            'title': 'Branch',
                            'value': 'my-branch',
                        },
                    ],
                    'image_url': attachment.get_absolute_url(),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/',
                    'text': '',
                    'pretext': (
                        'New update from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_closed_review_request_as_submitted(self):
        """Testing MattermostIntegration notifies on closing review request as
        submitted
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: Closed as completed by Test User: '
                        'http://example.com/r/1/'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/',
                    'text': None,
                    'pretext': (
                        'Closed as completed by '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_closed_review_request_as_discarded(self):
        """Testing MattermostIntegration notifies on closing review request as
        discarded
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: Discarded by Test User: '
                        'http://example.com/r/1/'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/',
                    'text': None,
                    'pretext': (
                        'Discarded by '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    @add_fixtures(['test_site'])
    def test_notify_closed_review_request_with_local_site(self):
        """Testing MattermostIntegration notifies on closing review request
        with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: Closed as completed by Test User: '
                        'http://example.com/s/local-site-1/r/1/'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/s/local-site-1/r/1/',
                    'text': None,
                    'pretext': (
                        'Closed as completed by '
                        '<http://example.com/s/local-site-1/users/test/'
                        '|Test User>'
                    ),
                }],
            })

    def test_notify_reopened_review_request(self):
        """Testing MattermostIntegration notifies on reopened review request"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: Reopened by Test User: '
                        'http://example.com/r/1/'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/',
                    'text': 'My description.',
                    'pretext': (
                        'Reopened by '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    @add_fixtures(['test_site'])
    def test_notify_reopened_review_request_with_local_site(self):
        """Testing MattermostIntegration notifies on reopened review request
        with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: Reopened by Test User: '
                        'http://example.com/s/local-site-1/r/1/'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/s/local-site-1/r/1/',
                    'text': 'My description.',
                    'pretext': (
                        'Reopened by '
                        '<http://example.com/s/local-site-1/users/test/'
                        '|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_with_body_top(self):
        """Testing MattermostIntegration notifies on new review with body_
        top
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New review from Test User: '
                        'http://example.com/r/1/#review1'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review1',
                    'text': 'This is my review.',
                    'pretext': (
                        'New review from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    @add_fixtures(['test_site'])
    def test_notify_new_review_with_local_site(self):
        """Testing MattermostIntegration notifies on new review with local
        site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New review from Test User: '
                        'http://example.com/s/local-site-1/r/1/#review1'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': (
                        'http://example.com/s/local-site-1/r/1/#review1'
                    ),
                    'text': 'This is my review.',
                    'pretext': (
                        'New review from '
                        '<http://example.com/s/local-site-1/users/test/'
                        '|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_with_comments(self):
        """Testing MattermostIntegration notifies on new review with only
        comments
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New review from Test User: '
                        'http://example.com/r/1/#review1'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review1',
                    'text': 'My general comment.',
                    'pretext': (
                        'New review from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_with_one_open_issue(self):
        """Testing MattermostIntegration notifies on new review with 1 open
        issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': 'warning',
                    'fallback': (
                        '#1: New review from Test User (1 issue): '
                        'http://example.com/r/1/#review1'
                    ),
                    'fields': [{
                        'title': 'Open Issues',
                        'value': ':warning: 1 issue',
                        'short': True,
                    }],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review1',
                    'text': 'My general comment.',
                    'pretext': (
                        'New review from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_with_open_issues(self):
        """Testing MattermostIntegration notifies on new review with > 1 open
        issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': 'warning',
                    'fallback': (
                        '#1: New review from Test User (2 issues): '
                        'http://example.com/r/1/#review1'
                    ),
                    'fields': [{
                        'title': 'Open Issues',
                        'value': ':warning: 2 issues',
                        'short': True,
                    }],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review1',
                    'text': 'My general comment.',
                    'pretext': (
                        'New review from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_with_ship_it(self):
        """Testing MattermostIntegration notifies on new review with Ship
        It!
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': 'good',
                    'fallback': (
                        '#1: New review from Test User (Ship it!): '
                        'http://example.com/r/1/#review1'
                    ),
                    'fields': [{
                        'title': 'Ship it!',
                        'value': ':white_check_mark:',
                        'short': True,
                    }],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review1',
                    'text': '',
                    'pretext': (
                        'New review from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_with_ship_it_and_custom_body_top(self):
        """Testing MattermostIntegration notifies on new review with Ship It
        and custom body_top
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': 'good',
                    'fallback': (
                        '#1: New review from Test User (Ship it!): '
                        'http://example.com/r/1/#review1'
                    ),
                    'fields': [{
                        'title': 'Ship it!',
                        'value': ':white_check_mark:',
                        'short': True,
                    }],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review1',
                    'text': 'This is body_top.',
                    'pretext': (
                        'New review from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_with_ship_it_and_one_open_issue(self):
        """Testing MattermostIntegration notifies on new review with Ship It!
        and 1 open issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': 'warning',
                    'fallback': (
                        '#1: New review from Test User '
                        '(Fix it, then Ship it!): '
                        'http://example.com/r/1/#review1'
                    ),
                    'fields': [{
                        'title': 'Fix it, then Ship it!',
                        'value': ':warning: 1 issue',
                        'short': True,
                    }],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review1',
                    'text': '',
                    'pretext': (
                        'New review from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_review_with_ship_it_and_open_issues(self):
        """Testing MattermostIntegration notifies on new review with Ship It!
        and > 1 open issues
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': 'warning',
                    'fallback': (
                        '#1: New review from Test User '
                        '(Fix it, then Ship it!): '
                        'http://example.com/r/1/#review1'
                    ),
                    'fields': [{
                        'title': 'Fix it, then Ship it!',
                        'value': ':warning: 2 issues',
                        'short': True,
                    }],
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review1',
                    'text': '',
                    'pretext': (
                        'New review from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def test_notify_new_reply_with_body_top(self):
        """Testing MattermostIntegration notifies on new reply with body_top"""
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New reply from Test User: '
                        'http://example.com/r/1/#review2'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review2',
                    'text': 'This is body_top.',
                    'pretext': (
                        'New reply from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    @add_fixtures(['test_site'])
    def test_notify_new_reply_with_local_site(self):
        """Testing MattermostIntegration notifies on new reply with local
        site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New reply from Test User: '
                        'http://example.com/s/local-site-1/r/1/#review2'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': (
                        'http://example.com/s/local-site-1/r/1/#review2'
                    ),
                    'text': 'This is body_top.',
                    'pretext': (
                        'New reply from '
                        '<http://example.com/s/local-site-1/users/test/'
                        '|Test User>'
                    ),
                }],
            })

    def test_notify_new_reply_with_comment(self):
        """Testing MattermostIntegration notifies on new reply with comment"""
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            target_people=[self.user],
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
                'username': 'RB User',
                'icon_url': self.integration.LOGO_URL,
                'attachments': [{
                    'color': self.integration.DEFAULT_COLOR,
                    'fallback': (
                        '#1: New reply from Test User: '
                        'http://example.com/r/1/#review2'
                    ),
                    'title': '#1: Test Review Request',
                    'title_link': 'http://example.com/r/1/#review2',
                    'text': 'This is a comment.',
                    'pretext': (
                        'New reply from '
                        '<http://example.com/users/test/|Test User>'
                    ),
                }],
            })

    def _create_config(self, with_local_site=False):
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
        config.set('webhook_url', 'http://example.com/mattermost-url/')
        config.set('conditions', condition_set.serialize())
        config.save()

        return config
