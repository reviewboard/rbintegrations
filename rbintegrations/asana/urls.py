"""URL definitions for the Asana integration."""

from django.urls import include, path

from rbintegrations.asana.views import (AsanaTaskSearchView,
                                        AsanaWorkspaceListView)


localsite_urlpatterns = [
    path('task-search/<int:review_request_id>/',
         AsanaTaskSearchView.as_view(),
         name='asana-task-search'),
]

urlpatterns = [
    path('workspaces/', AsanaWorkspaceListView.as_view(),
         name='asana-workspace-list'),
    path('s/<local_site_name>/', include(localsite_urlpatterns)),
]
urlpatterns += localsite_urlpatterns
