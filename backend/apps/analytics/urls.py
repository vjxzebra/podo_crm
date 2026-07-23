from django.urls import path

from apps.analytics.views import AnalyticsExportView, AnalyticsView, OverviewView

urlpatterns = [
    path("overview", OverviewView.as_view(), name="overview"),
    path("analytics/export", AnalyticsExportView.as_view(), name="analytics-export"),
    path("analytics", AnalyticsView.as_view(), name="analytics"),
]
