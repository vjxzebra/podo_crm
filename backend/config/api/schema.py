from typing import Any


def require_work_item_update_version(
    result: dict[str, Any],
    generator: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Keep optimistic-locking version required despite generic PATCH partial semantics."""
    del generator, kwargs
    request_body = result["paths"]["/api/v1/work-items/{work_item_id}"]["patch"]["requestBody"]
    request_body["required"] = True
    for media_type in request_body["content"].values():
        reference = media_type["schema"]["$ref"]
        component_name = reference.rsplit("/", maxsplit=1)[-1]
        component = result["components"]["schemas"][component_name]
        required = component.setdefault("required", [])
        if "version" not in required:
            required.append("version")
    return result


def close_finance_mutation_request_schemas(
    result: dict[str, Any],
    generator: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Mirror strict finance runtime serializers in their published request schemas."""
    del generator, kwargs
    for path in (
        "/api/v1/payments",
        "/api/v1/payments/{payment_id}/refunds",
        "/api/v1/cash-movements",
        "/api/v1/cash-shifts/{shift_id}/close",
    ):
        request_body = result["paths"][path]["post"]["requestBody"]
        for media_type in request_body["content"].values():
            reference = media_type["schema"]["$ref"]
            component_name = reference.rsplit("/", maxsplit=1)[-1]
            result["components"]["schemas"][component_name]["additionalProperties"] = False
    return result
