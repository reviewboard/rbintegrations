"""URL definitions for the Trello integration."""

from django.urls import include, path

from rbintegrations.trello.views import TrelloCardSearchView


localsite_urlpatterns = [
    path('card-search/<int:review_request_id>/',
         TrelloCardSearchView.as_view(),
         name='trello-card-search'),
]

urlpatterns = [
    path('s/<local_site_name>/', include(localsite_urlpatterns)),
]
urlpatterns += localsite_urlpatterns
