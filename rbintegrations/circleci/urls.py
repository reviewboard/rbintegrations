from __future__ import unicode_literals

from django.conf.urls import url

from rbintegrations.circleci.views import CircleCIWebHookView


urlpatterns = [
    url(r'^webhook/$', CircleCIWebHookView.as_view(),
        name='circle-ci-webhook'),
]
