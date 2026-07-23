from django.urls import path

from apps.visits.views import (
    StartVisitView,
    VisitDetailView,
    VisitFinishView,
    VisitMaterialOptionListView,
    VisitPhotoContentView,
    VisitPhotoDetailView,
    VisitPhotoFinalizeView,
    VisitPhotoUploadIntentView,
    VisitRecommendationDetailView,
    VisitRecommendationListCreateView,
)

urlpatterns = [
    path(
        "appointments/<uuid:appointment_id>/start-visit",
        StartVisitView.as_view(),
        name="visit-start",
    ),
    path("visits/<uuid:visit_id>", VisitDetailView.as_view(), name="visit-detail"),
    path("visits/<uuid:visit_id>/finish", VisitFinishView.as_view(), name="visit-finish"),
    path(
        "visits/<uuid:visit_id>/material-options",
        VisitMaterialOptionListView.as_view(),
        name="visit-material-options",
    ),
    path(
        "visits/<uuid:visit_id>/photos/upload-intents",
        VisitPhotoUploadIntentView.as_view(),
        name="visit-photo-upload-intent",
    ),
    path(
        "visits/<uuid:visit_id>/photos",
        VisitPhotoFinalizeView.as_view(),
        name="visit-photo-finalize",
    ),
    path(
        "visits/<uuid:visit_id>/photos/<uuid:photo_id>",
        VisitPhotoDetailView.as_view(),
        name="visit-photo-detail",
    ),
    path(
        "visit-photo-content",
        VisitPhotoContentView.as_view(),
        name="visit-photo-content",
    ),
    path(
        "visits/<uuid:visit_id>/recommendations",
        VisitRecommendationListCreateView.as_view(),
        name="visit-recommendation-create",
    ),
    path(
        "visits/<uuid:visit_id>/recommendations/<uuid:recommendation_id>",
        VisitRecommendationDetailView.as_view(),
        name="visit-recommendation-update",
    ),
]
