from django.urls import path

from rbintegrations.circleci.views import CircleCIWebHookView


urlpatterns = [
    path('webhook/', CircleCIWebHookView.as_view(), name='circle-ci-webhook'),
]
