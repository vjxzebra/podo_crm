from django.urls import path

from apps.global_search.views import GlobalSearchView

urlpatterns = [
    path("search", GlobalSearchView.as_view(), name="global-search"),
]
