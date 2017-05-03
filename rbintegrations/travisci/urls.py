from __future__ import unicode_literals

from django.conf.urls import url

from rbintegrations.travisci.views import TravisCIWebHookView


urlpatterns = [
    url(r'^webhook/$', TravisCIWebHookView.as_view(),
        name='travis-ci-webhook'),
]
