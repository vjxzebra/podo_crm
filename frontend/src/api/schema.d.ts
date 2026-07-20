// Generated from backend/openapi/schema.json. Do not edit by hand.
export interface paths {
    "/api/v1/contract/fixture": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return the technical success or error contract fixture */
        get: operations["contract_fixture_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        ContractFixture: {
            correlation_id: string;
            message: string;
            status: components["schemas"]["StatusEnum"];
        };
        ErrorEnvelope: {
            code: string;
            correlation_id: string;
            fields: {
                [key: string]: string[];
            };
            message: string;
        };
        /**
         * @description * `ok` - ok
         * @enum {string}
         */
        StatusEnum: "ok";
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    contract_fixture_retrieve: {
        parameters: {
            query?: {
                outcome?: "error" | "success";
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContractFixture"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
}
