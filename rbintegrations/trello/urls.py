"""URL definitions for the Trello integration."""

from __future__ import unicode_literals

from django.conf.urls import include, url

from rbintegrations.trello.views import TrelloCardSearchView


localsite_urlpatterns = [
    url(r'^card-search/(?P<review_request_id>\d+)/$',
        TrelloCardSearchView.as_view(),
        name='trello-card-search'),
]

urlpatterns = [
    url(r'^s/(?P<local_site_name>[\w\.-]+)/',
        include(localsite_urlpatterns)),
]
urlpatterns += localsite_urlpatterns
