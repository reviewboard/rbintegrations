"""URL definitions for the Asana integration."""

from __future__ import unicode_literals

from django.conf.urls import include, url

from rbintegrations.asana.views import (AsanaTaskSearchView,
                                        AsanaWorkspaceListView)


localsite_urlpatterns = [
    url(r'^task-search/(?P<review_request_id>\d+)/$',
        AsanaTaskSearchView.as_view(),
        name='asana-task-search'),
]

urlpatterns = [
    url(r'^workspaces/$', AsanaWorkspaceListView.as_view(),
        name='asana-workspace-list'),
    url(r'^s/(?P<local_site_name>[\w\.-]+)/',
        include(localsite_urlpatterns)),
]
urlpatterns += localsite_urlpatterns
