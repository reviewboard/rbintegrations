"""Unit tests for the Asana integration."""

from __future__ import unicode_literals

from django.http import HttpResponse
from reviewboard.site.urlresolvers import local_site_reverse

from rbintegrations.asana.integration import AsanaIntegration
from rbintegrations.asana.views import (AsanaTaskSearchView,
                                        AsanaWorkspaceListView)
from rbintegrations.testing.testcases import IntegrationTestCase


class AsanaIntegrationTests(IntegrationTestCase):
    """Tests for Asana."""

    integration_cls = AsanaIntegration
    fixtures = ['test_users', 'test_site']

    def test_workspace_list(self):
        """Testing AsanaWorkspaceListView"""
        self.spy_on(AsanaWorkspaceListView.get,
                    owner=AsanaWorkspaceListView,
                    call_fake=lambda self, request: HttpResponse(
                        '{}', content_type='application/json'))

        rsp = self.client.get(local_site_reverse('asana-workspace-list'))

        self.assertEqual(rsp.status_code, 200)

    def test_task_search(self):
        """Testing AsanaTaskSearchView"""
        self.spy_on(AsanaTaskSearchView.get,
                    owner=AsanaTaskSearchView,
                    call_fake=lambda self, request, **kwargs: HttpResponse(
                        '{}', content_type='application/json'))

        review_request = self.create_review_request(public=True)
        rsp = self.client.get(local_site_reverse(
            'asana-task-search',
            kwargs={
                'review_request_id': review_request.display_id,
            }))

        self.assertEqual(rsp.status_code, 200)

    def test_task_search_unpublished(self):
        """Testing AsanaTaskSearchView with an unpublished review request"""
        self.spy_on(AsanaTaskSearchView.get,
                    owner=AsanaTaskSearchView,
                    call_fake=lambda self, request, **kwargs: HttpResponse(
                        '{}', content_type='application/json'))

        review_request = self.create_review_request(public=False)
        self.client.login(username='dopey', password='dopey')
        rsp = self.client.get(local_site_reverse(
            'asana-task-search',
            kwargs={
                'review_request_id': review_request.display_id,
            }))

        self.assertEqual(rsp.status_code, 403)

    def test_task_search_with_local_site(self):
        """Testing AsanaTaskSearchView with a Local Site"""
        self.spy_on(AsanaTaskSearchView.get,
                    owner=AsanaTaskSearchView,
                    call_fake=lambda self, request, **kwargs: HttpResponse(
                        '{}', content_type='application/json'))

        self.client.login(username='doc', password='doc')
        review_request = self.create_review_request(public=True,
                                                    with_local_site=True)
        rsp = self.client.get(local_site_reverse(
            'asana-task-search',
            local_site_name=review_request.local_site.name,
            kwargs={
                'review_request_id': review_request.display_id,
            }))

        self.assertEqual(rsp.status_code, 200)

    def test_task_search_with_local_site_no_access(self):
        """Testing AsanaTaskSearchView with a Local Site that the user does not
        have access to
        """
        self.spy_on(AsanaTaskSearchView.get,
                    owner=AsanaTaskSearchView,
                    call_fake=lambda self, request, **kwargs: HttpResponse(
                        '{}', content_type='application/json'))

        self.client.login(username='dopey', password='dopey')
        review_request = self.create_review_request(public=True,
                                                    with_local_site=True)
        rsp = self.client.get(local_site_reverse(
            'asana-task-search',
            local_site_name=review_request.local_site.name,
            kwargs={
                'review_request_id': review_request.display_id,
            }))

        self.assertEqual(rsp.status_code, 403)
