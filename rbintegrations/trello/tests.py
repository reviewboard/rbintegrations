"""Unit tests for the Trello integration."""

from __future__ import unicode_literals

from django.http import HttpResponse
from reviewboard.site.urlresolvers import local_site_reverse

from rbintegrations.testing.testcases import IntegrationTestCase
from rbintegrations.trello.integration import TrelloIntegration
from rbintegrations.trello.views import TrelloCardSearchView


class TrelloIntegrationTests(IntegrationTestCase):
    """Tests for Trello."""

    integration_cls = TrelloIntegration
    fixtures = ['test_users', 'test_site']

    def test_card_search(self):
        """Testing TrelloCardSearchView"""
        self.spy_on(TrelloCardSearchView.get,
                    owner=TrelloCardSearchView,
                    call_fake=lambda self, request, **kwargs: HttpResponse(
                        '{}', content_type='application/json'))

        review_request = self.create_review_request(public=True)
        rsp = self.client.get(local_site_reverse(
            'trello-card-search',
            kwargs={
                'review_request_id': review_request.display_id,
            }))

        self.assertEqual(rsp.status_code, 200)

    def test_card_search_unpublished(self):
        """Testing TrelloCardSearchView with an unpublished review request"""
        self.spy_on(TrelloCardSearchView.get,
                    owner=TrelloCardSearchView,
                    call_fake=lambda self, request, **kwargs: HttpResponse(
                        '{}', content_type='application/json'))

        review_request = self.create_review_request(public=False)
        rsp = self.client.get(local_site_reverse(
            'trello-card-search',
            kwargs={
                'review_request_id': review_request.display_id,
            }))

        self.assertEqual(rsp.status_code, 403)

    def test_card_search_with_local_site(self):
        """Testing TrelloCardSearchView with a Local Site"""
        self.spy_on(TrelloCardSearchView.get,
                    owner=TrelloCardSearchView,
                    call_fake=lambda self, request, **kwargs: HttpResponse(
                        '{}', content_type='application/json'))

        self.client.login(username='doc', password='doc')
        review_request = self.create_review_request(public=True,
                                                    with_local_site=True)
        rsp = self.client.get(local_site_reverse(
            'trello-card-search',
            local_site_name=review_request.local_site.name,
            kwargs={
                'review_request_id': review_request.display_id,
            }))

        self.assertEqual(rsp.status_code, 200)

    def test_card_search_with_local_site_no_access(self):
        """Testing TrelloCardSearchView with a Local Site that the user does
        not have access to
        """
        self.spy_on(TrelloCardSearchView.get,
                    owner=TrelloCardSearchView,
                    call_fake=lambda self, request, **kwargs: HttpResponse(
                        '{}', content_type='application/json'))

        self.client.login(username='dopey', password='dopey')
        review_request = self.create_review_request(public=True,
                                                    with_local_site=True)
        rsp = self.client.get(local_site_reverse(
            'trello-card-search',
            local_site_name=review_request.local_site.name,
            kwargs={
                'review_request_id': review_request.display_id,
            }))

        self.assertEqual(rsp.status_code, 403)
