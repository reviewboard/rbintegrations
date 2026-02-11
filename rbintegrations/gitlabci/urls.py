"""URLs for the GitLab CI integration.

Version Added:
    5.0
"""

from __future__ import annotations

from django.urls import path

from rbintegrations.gitlabci.views import GitlabCIWebHookView


urlpatterns = [
    path(
        'webhook/',
        GitlabCIWebHookView.as_view(),
        name='gitlab-ci-webhook',
    ),
]
