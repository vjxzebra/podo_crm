from django.urls import path

from apps.discounts.views import DiscountDetailView, DiscountListCreateView, LoyaltyPolicyView

urlpatterns = [
    path("discounts", DiscountListCreateView.as_view(), name="discount-list-create"),
    path("discounts/<uuid:discount_id>", DiscountDetailView.as_view(), name="discount-detail"),
    path("loyalty-policy", LoyaltyPolicyView.as_view(), name="loyalty-policy"),
]
