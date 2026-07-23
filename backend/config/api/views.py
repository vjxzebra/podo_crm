from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api.exceptions import ApiProblem
from config.api.serializers import ContractFixtureSerializer, ErrorEnvelopeSerializer
from config.middleware import get_request_id


class ContractFixtureView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="contract_fixture_retrieve",
        summary="Return the technical success or error contract fixture",
        parameters=[
            OpenApiParameter(
                name="outcome",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=["success", "error"],
                default="success",
            )
        ],
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=ContractFixtureSerializer,
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "status": "ok",
                            "message": "API contract is available.",
                            "correlation_id": "tp102-example",
                        },
                    )
                ],
            ),
            status.HTTP_422_UNPROCESSABLE_ENTITY: OpenApiResponse(
                response=ErrorEnvelopeSerializer,
                examples=[
                    OpenApiExample(
                        "Error",
                        value={
                            "code": "contract_fixture_error",
                            "message": "Requested the error contract fixture.",
                            "fields": {
                                "outcome": ["Use success to receive a successful response."]
                            },
                            "correlation_id": "tp102-example",
                        },
                    )
                ],
            ),
        },
        tags=["platform"],
    )
    def get(self, request: Request) -> Response:
        outcome = request.query_params.get("outcome", "success")
        if outcome == "error":
            raise ApiProblem(
                code="contract_fixture_error",
                message="Requested the error contract fixture.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={"outcome": ["Use success to receive a successful response."]},
            )
        if outcome != "success":
            raise ValidationError({"outcome": ["Allowed values: success, error."]})

        return Response(
            {
                "status": "ok",
                "message": "API contract is available.",
                "correlation_id": get_request_id(request),
            }
        )
