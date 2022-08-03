from django.urls import path

from rbintegrations.travisci.views import TravisCIWebHookView


urlpatterns = [
    path('webhook/', TravisCIWebHookView.as_view(), name='travis-ci-webhook'),
]
