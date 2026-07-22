from django.urls import path

from apps.analytics.views import AnalyticsView, OverviewView

urlpatterns = [
    path("overview", OverviewView.as_view(), name="overview"),
    path("analytics", AnalyticsView.as_view(), name="analytics"),
]
