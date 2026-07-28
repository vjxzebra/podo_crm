// Generated from backend/openapi/schema.json. Do not edit by hand.
export interface paths {
    "/api/v1/analytics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return ledger- and visit-derived clinic analytics for an administrator */
        get: operations["analytics_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export the current aggregate administrator analytics projection as safe CSV */
        get: operations["analytics_export"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/appointment-status-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List the eight protected appointment status configurations */
        get: operations["appointment_status_config_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/appointment-status-configs/{code}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update a status label, color and manual role flags without changing its code */
        patch: operations["appointment_status_config_update"];
        trace?: never;
    };
    "/api/v1/appointments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create an appointment inside clinic hours with role and occupancy protection */
        post: operations["appointment_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/appointments/{appointment_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return role-scoped appointment details and allowed actions */
        get: operations["appointment_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Edit or reschedule a role-scoped appointment with optimistic concurrency */
        patch: operations["appointment_update"];
        trace?: never;
    };
    "/api/v1/appointments/{appointment_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel an eligible appointment with a required reason */
        post: operations["appointment_cancel"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/appointments/{appointment_id}/start-visit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start one visit for an arrived appointment */
        post: operations["visit_start"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/appointments/{appointment_id}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Apply an allowed manual appointment status transition */
        post: operations["appointment_status_transition"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/appointments/availability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return free slots inside clinic hours without specialist or room conflicts */
        get: operations["appointment_availability_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audit-events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List append-only audit events for an administrator */
        get: operations["audit_event_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audit-events/{event_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return redacted before/after details for one audit event */
        get: operations["audit_event_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audit-events/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export the filtered administrator audit journal as safe CSV */
        get: operations["audit_event_export"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/change-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Change the current user's password and revoke other sessions */
        post: operations["auth_change_password"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/first-login-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Replace a temporary password before entering the workspace */
        post: operations["auth_first_login_password"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create a server session */
        post: operations["auth_login"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Destroy the current server session */
        post: operations["auth_logout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/booking-request-integration": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return safe booking-request API credential metadata */
        get: operations["booking_request_integration_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/booking-request-integration/token/rotate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate or rotate the booking-request API token */
        post: operations["booking_request_integration_token_rotate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/booking-requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List booking requests visible to admin and reception */
        get: operations["booking_request_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/booking-requests/{booking_request_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Retrieve one booking request */
        get: operations["booking_request_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/booking-requests/{booking_request_id}/process": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Idempotently mark one booking request as processed */
        post: operations["booking_request_process"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/calendar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return a role-scoped day or week calendar read model */
        get: operations["calendar_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cash-movements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post a cash deposit or withdrawal into the actor's open shift */
        post: operations["cash_movement_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cash-shifts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List role-scoped cash-shift history with stable keyset paging */
        get: operations["cash_shift_list"];
        put?: never;
        /** Open one cash shift for the current employee */
        post: operations["cash_shift_open"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cash-shifts/{shift_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return one role-scoped cash shift with its complete immutable ledger */
        get: operations["cash_shift_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cash-shifts/{shift_id}/close": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Close one owned cash shift, or any shift as admin, after reconciliation */
        post: operations["cash_shift_close"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cash-shifts/{shift_id}/close-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Preview authoritative cash reconciliation and unpaid warning */
        get: operations["cash_shift_close_preview"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cash-shifts/{shift_id}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export one role-scoped cash shift and its append-only ledger as safe CSV */
        get: operations["cash_shift_export"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cash-shifts/current": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return the current employee's open shift and ledger-derived totals */
        get: operations["cash_shift_current"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cash-shifts/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export filtered role-scoped cash-shift summaries as safe CSV */
        get: operations["cash_shift_history_export"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/clinic-profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return the singleton clinic profile */
        get: operations["clinic_profile_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update clinic contact and identity fields */
        patch: operations["clinic_profile_update"];
        trace?: never;
    };
    "/api/v1/clinic-profile/logo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read the private clinic logo for an authenticated employee */
        get: operations["clinic_logo_retrieve"];
        /** Validate and replace the private clinic logo */
        put: operations["clinic_logo_update"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/clinic-workdays": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return the single clinic-wide weekly schedule in Europe/Kyiv */
        get: operations["clinic_workday_list"];
        /** Atomically replace work hours and non-overlapping breaks for all seven days */
        put: operations["clinic_workday_update"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
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
    "/api/v1/finance/operations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search and keyset-page receivable lifecycle and posted finance operations */
        get: operations["finance_operation_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/finance/operations/{operation_type}/{operation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Resolve an exact role-scoped finance operation deep link */
        get: operations["finance_operation_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/finance/operations/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export filtered admin finance-operation journal as safe CSV */
        get: operations["finance_operation_export"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/integrations/booking-requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create a booking request from a server-side integration */
        post: operations["external_booking_request_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/integrations/telegram/webhook": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Receive Telegram webhook updates */
        post: operations["telegram_webhook_receive"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/materials": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search and filter the administrator material catalog with stock projections */
        get: operations["inventory_material_list"];
        put?: never;
        /** Create an administrator material catalog record */
        post: operations["inventory_material_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/materials/{material_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return administrator material details and current stock projections */
        get: operations["inventory_material_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Edit or deactivate a material while protecting unit and historical stock identity */
        patch: operations["inventory_material_update"];
        trace?: never;
    };
    "/api/v1/inventory/materials/{material_id}/lots": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List material lots with expiry, usability and FEFO projections */
        get: operations["inventory_material_lot_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/movements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search and cursor-page the append-only stock movement journal */
        get: operations["inventory_movement_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/movements/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export the filtered append-only stock movement journal as safe CSV */
        get: operations["inventory_movement_export"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/operations/{operation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return a read-only inventory operation with all append-only movements */
        get: operations["inventory_operation_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/receipts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post a multi-line material receipt atomically */
        post: operations["inventory_receipt_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/stocktakes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Freeze an immutable physical-count draft against the current lot balances */
        post: operations["inventory_stocktake_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/stocktakes/{stocktake_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return the immutable physical-count draft or posted stocktake */
        get: operations["inventory_stocktake_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/stocktakes/{stocktake_id}/post": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post a stocktake atomically as append-only lot adjustments */
        post: operations["inventory_stocktake_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/stocktakes/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return the current per-lot balances for a physical stocktake */
        get: operations["inventory_stocktake_preview"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/suppliers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search and filter the administrator supplier directory */
        get: operations["inventory_supplier_list"];
        put?: never;
        /** Create an administrator supplier directory record */
        post: operations["inventory_supplier_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/inventory/suppliers/{supplier_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return administrator supplier details and historical lot count */
        get: operations["inventory_supplier_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Edit, deactivate or reactivate a supplier without changing lot history */
        patch: operations["inventory_supplier_update"];
        trace?: never;
    };
    "/api/v1/inventory/write-offs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post a locked manual stock write-off without allowing a negative balance */
        post: operations["inventory_manual_writeoff_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List recipient-owned internal notifications */
        get: operations["notification_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications/{notification_id}/read": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Idempotently mark one recipient-owned notification as read */
        post: operations["notification_read"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications/read-all": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Idempotently mark all current recipient notifications as read */
        post: operations["notification_read_all"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return a role-scoped operational overview for one local clinic date */
        get: operations["overview_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/password-reset-requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List pending password reset requests for an administrator */
        get: operations["password_reset_request_list"];
        put?: never;
        /** Create an enumeration-safe password reset request */
        post: operations["password_reset_request_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search the role-scoped patient directory with cursor pagination */
        get: operations["patient_list"];
        put?: never;
        /** Create a patient and return role-safe possible phone duplicates */
        post: operations["patient_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients/{patient_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Retrieve a role-scoped patient card projection */
        get: operations["patient_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update a patient through the actor's safe role projection */
        patch: operations["patient_update"];
        trace?: never;
    };
    "/api/v1/patients/{patient_id}/photos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List completed visit photos after medical object-scope authorization */
        get: operations["patient_photo_archive"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients/{patient_id}/recommendations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List patient recommendations with eligible completed visits */
        get: operations["patient_recommendation_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/patients/{patient_id}/visits": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List completed visits through a role-safe patient projection */
        get: operations["patient_visit_history"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/payments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post one server-derived full payment into the actor's open shift */
        post: operations["payment_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/payments/{payment_id}/refunds": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post one server-derived full refund into the actor's open shift */
        post: operations["refund_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rooms": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List active and inactive rooms for the single clinic location */
        get: operations["room_list"];
        put?: never;
        /** Create a room for the single clinic location */
        post: operations["room_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rooms/{room_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Rename, deactivate or reactivate a room without deleting history */
        patch: operations["room_update"];
        trace?: never;
    };
    "/api/v1/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search role-scoped CRM objects and return canonical deep links */
        get: operations["global_search_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/services": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search services; non-admin employees receive active picker records only */
        get: operations["service_list"];
        put?: never;
        /** Create a service in the administrator catalog */
        post: operations["service_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/services/{service_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return a service; non-admin employees can retrieve active picker records only */
        get: operations["service_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Edit, deactivate or reactivate a service without deleting history */
        patch: operations["service_update"];
        trace?: never;
    };
    "/api/v1/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return the authenticated user and server-authorized routes */
        get: operations["session_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/telegram/link-intents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create a one-time Telegram deep link for current user */
        post: operations["telegram_link_intent_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/telegram/subscription": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return current user's Telegram subscription status */
        get: operations["telegram_subscription_retrieve"];
        put?: never;
        post?: never;
        /** Disable current user's Telegram subscription */
        delete: operations["telegram_subscription_disconnect"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List and filter employees for an administrator */
        get: operations["team_user_list"];
        put?: never;
        /** Create an employee with initial password policy */
        post: operations["team_user_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Return one employee profile */
        get: operations["team_user_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update contacts, role or active state with last-admin protection */
        patch: operations["team_user_update"];
        trace?: never;
    };
    "/api/v1/users/{user_id}/deactivate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Deactivate an employee and revoke their sessions */
        post: operations["team_user_deactivate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users/{user_id}/temporary-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Set a temporary password and revoke every user session */
        post: operations["user_temporary_password_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/visit-photo-content": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read private photo bytes through an expiring signed URL */
        get: operations["visit_photo_content_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/visits/{visit_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read a role-scoped clinical visit workspace */
        get: operations["visit_retrieve"];
        /** Save a versioned visit draft without posting side effects */
        put: operations["visit_draft_update"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/visits/{visit_id}/finish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Atomically finish a visit, post stock and create one receivable */
        post: operations["visit_finish"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/visits/{visit_id}/material-options": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search role-scoped usable material lots for a visit draft */
        get: operations["visit_material_option_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/visits/{visit_id}/photos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Validate, canonicalize and finalize one private visit photo */
        post: operations["visit_photo_finalize"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/visits/{visit_id}/photos/{photo_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Authorize and return metadata with five-minute signed photo URLs */
        get: operations["visit_photo_retrieve"];
        put?: never;
        post?: never;
        /** Delete one photo while its visit remains a draft */
        delete: operations["visit_photo_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/visits/{visit_id}/photos/upload-intents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create a short-lived private visit-photo upload intent */
        post: operations["visit_photo_upload_intent_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/visits/{visit_id}/recommendations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add an authored recommendation to a completed visit */
        post: operations["visit_recommendation_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/visits/{visit_id}/recommendations/{recommendation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Refresh one recommendation after medical object-scope authorization */
        get: operations["visit_recommendation_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update an authored recommendation with optimistic versioning */
        patch: operations["visit_recommendation_update"];
        trace?: never;
    };
    "/api/v1/work-items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List role-scoped internal work items */
        get: operations["work_item_list"];
        put?: never;
        /** Create an internal work item */
        post: operations["work_item_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/work-items/{work_item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Edit, complete, or reopen a role-scoped internal work item */
        patch: operations["work_item_update"];
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        AnalyticsAppliedFilters: {
            service: components["schemas"]["AnalyticsOption"] | null;
            specialist: components["schemas"]["AnalyticsOption"] | null;
        };
        AnalyticsKpi: {
            average_check_minor: number;
            average_return_interval_days: number | null;
            canceled_appointments: number;
            completed_visits: number;
            new_patients: number;
            no_show_appointments: number;
            payment_count: number;
            returning_patient_rate_bps: number;
            returning_patients: number;
            revenue_minor: number;
            served_patients: number;
        };
        AnalyticsOption: {
            id: string;
            is_active: boolean;
            name: string;
        };
        AnalyticsOutcome: {
            code: string;
            count: number;
            label: string;
        };
        AnalyticsPeriod: {
            bucket: components["schemas"]["BucketEnum"];
            /** Format: date */
            date_from: string;
            /** Format: date */
            date_to: string;
            timezone: string;
        };
        AnalyticsResponse: {
            appointment_outcomes: components["schemas"]["AnalyticsOutcome"][];
            available_services: components["schemas"]["AnalyticsOption"][];
            available_specialists: components["schemas"]["AnalyticsOption"][];
            filters: components["schemas"]["AnalyticsAppliedFilters"];
            kpis: components["schemas"]["AnalyticsKpi"];
            period: components["schemas"]["AnalyticsPeriod"];
            service_ranking: components["schemas"]["AnalyticsServiceRanking"][];
            specialist_performance: components["schemas"]["AnalyticsSpecialistPerformance"][];
            trend: components["schemas"]["AnalyticsTrendPoint"][];
        };
        AnalyticsServiceRanking: {
            billed_total_minor: number;
            code: string;
            /** Format: uuid */
            id: string;
            name: string;
            quantity: number;
            visit_count: number;
        };
        AnalyticsSpecialistPerformance: {
            available_minutes: number;
            completed_visits: number;
            id: number;
            is_active: boolean;
            name: string;
            revenue_minor: number;
            scheduled_minutes: number;
            utilization_bps: number;
        };
        AnalyticsTrendPoint: {
            /** Format: date */
            date_from: string;
            /** Format: date */
            date_to: string;
            label: string;
            revenue_minor: number;
            visits: number;
        };
        AppointmentCancelRequest: {
            reason: string;
            version: number;
        };
        AppointmentCreateRequest: {
            comment?: string;
            complaints?: string;
            /** @default false */
            has_no_complaints: boolean;
            /** Format: uuid */
            patient_id: string;
            /** Format: uuid */
            room_id: string;
            /** Format: uuid */
            service_id: string;
            specialist_id: number;
            /** Format: date-time */
            starts_at: string;
            /** @default NEW */
            status_code: components["schemas"]["AppointmentCreateStatusCodeEnum"];
        };
        /**
         * @description * `NEW` - NEW
         * @enum {string}
         */
        AppointmentCreateStatusCodeEnum: "NEW";
        AppointmentDetailResponse: {
            allowed_status_transitions: components["schemas"]["CalendarStatus"][];
            can_cancel: boolean;
            can_edit: boolean;
            can_reschedule: boolean;
            can_start_visit: boolean;
            cancellation_reason: string;
            comment: string;
            complaints: string;
            /** Format: date-time */
            created_at: string;
            duration_minutes: number;
            /** Format: date-time */
            ends_at: string;
            has_no_complaints: boolean;
            /** Format: uuid */
            id: string;
            patient: components["schemas"]["AppointmentPatient"];
            public_number: string;
            room: components["schemas"]["RoomSummary"];
            service: components["schemas"]["AppointmentService"];
            specialist: components["schemas"]["SpecialistSummary"];
            /** Format: date-time */
            starts_at: string;
            status: components["schemas"]["CalendarStatus"];
            /** Format: date-time */
            updated_at: string;
            version: number;
            /** Format: uuid */
            visit_id: string | null;
        };
        AppointmentPatient: {
            display_name: string;
            /** Format: uuid */
            id: string;
            phone: string;
            public_number: string;
        };
        AppointmentResponse: {
            cancellation_reason: string;
            comment: string;
            complaints: string;
            /** Format: date-time */
            created_at: string;
            duration_minutes: number;
            /** Format: date-time */
            ends_at: string;
            has_no_complaints: boolean;
            /** Format: uuid */
            id: string;
            patient: components["schemas"]["AppointmentPatient"];
            public_number: string;
            room: components["schemas"]["RoomSummary"];
            service: components["schemas"]["AppointmentService"];
            specialist: components["schemas"]["SpecialistSummary"];
            /** Format: date-time */
            starts_at: string;
            status: components["schemas"]["CalendarStatus"];
            /** Format: date-time */
            updated_at: string;
            version: number;
        };
        AppointmentService: {
            code: string;
            color: string;
            /** Format: uuid */
            id: string;
            name: string;
        };
        AppointmentStatusConfig: {
            readonly code: string;
            color: string;
            label: string;
            manual_admin?: boolean;
            manual_podologist?: boolean;
            manual_reception?: boolean;
            /** Format: date-time */
            readonly updated_at: string;
            version?: number;
        };
        AppointmentStatusConfigList: {
            statuses: components["schemas"]["AppointmentStatusConfig"][];
        };
        AppointmentStatusTransitionRequest: {
            status_code: components["schemas"]["AppointmentStatusTransitionStatusCodeEnum"];
            version: number;
        };
        /**
         * @description * `NEW` - NEW
         *     * `PENDING_CONFIRMATION` - PENDING_CONFIRMATION
         *     * `CONFIRMED` - CONFIRMED
         *     * `ARRIVED` - ARRIVED
         *     * `IN_PROGRESS` - IN_PROGRESS
         *     * `COMPLETED` - COMPLETED
         *     * `CANCELED` - CANCELED
         *     * `NO_SHOW` - NO_SHOW
         * @enum {string}
         */
        AppointmentStatusTransitionStatusCodeEnum: "NEW" | "PENDING_CONFIRMATION" | "CONFIRMED" | "ARRIVED" | "IN_PROGRESS" | "COMPLETED" | "CANCELED" | "NO_SHOW";
        AuditActor: {
            display_name: string;
            email: string;
            id: number | null;
            role: string;
        };
        AuditChange: {
            after: unknown;
            before: unknown;
            field: string;
        };
        AuditEventDetail: {
            action: string;
            readonly actor: components["schemas"]["AuditActor"];
            after?: unknown;
            before?: unknown;
            readonly changes: components["schemas"]["AuditChange"][];
            correlation_id: string;
            description?: string;
            /** Format: uuid */
            readonly id: string;
            note?: string;
            readonly object: components["schemas"]["AuditObject"];
            /** Format: date-time */
            readonly occurred_at: string;
            result?: string;
            section: string;
        };
        AuditEventListItem: {
            action: string;
            readonly actor: components["schemas"]["AuditActor"];
            description?: string;
            /** Format: uuid */
            readonly id: string;
            readonly object: components["schemas"]["AuditObject"];
            /** Format: date-time */
            readonly occurred_at: string;
            result?: string;
            section: string;
        };
        AuditEventListResponse: {
            events: components["schemas"]["AuditEventListItem"][];
            /** Format: uuid */
            next_cursor: string | null;
        };
        AuditObject: {
            id: string;
            label: string;
            type: string;
        };
        AvailabilityResponse: {
            /** Format: date */
            date: string;
            requested_room: components["schemas"]["RoomSummary"] | null;
            service: components["schemas"]["AvailabilityService"];
            slots: components["schemas"]["AvailabilitySlot"][];
            specialist: components["schemas"]["SpecialistSummary"];
            step_minutes: number;
            timezone: string;
        };
        AvailabilityService: {
            duration_minutes: number;
            /** Format: uuid */
            id: string;
            name: string;
        };
        AvailabilitySlot: {
            /** Format: date-time */
            ends_at: string;
            rooms: components["schemas"]["RoomSummary"][];
            /** Format: date-time */
            starts_at: string;
        };
        BookingRequest: {
            client_name?: string;
            contact_handle?: string;
            /** Format: date-time */
            readonly created_at: string;
            external_reference?: string;
            /** Format: uuid */
            readonly id: string;
            message?: string;
            phone?: string;
            /** Format: date-time */
            preferred_at?: string | null;
            /** Format: date-time */
            processed_at?: string | null;
            processed_by_display_name?: string;
            readonly public_number: string;
            service?: string;
            source: components["schemas"]["SourceEnum"];
            readonly source_label: string;
            status?: components["schemas"]["BookingRequestStatusEnum"];
            readonly status_label: string;
            /** Format: date-time */
            readonly updated_at: string;
            version?: number;
        };
        BookingRequestApiCredential: {
            readonly is_configured: boolean;
            /** Format: date-time */
            readonly rotated_at: string | null;
            readonly rotated_by_display_name: string;
            readonly token_hint: string;
            readonly version: number;
        };
        BookingRequestApiCredentialRotated: {
            readonly is_configured: boolean;
            /** Format: date-time */
            readonly rotated_at: string | null;
            readonly rotated_by_display_name: string;
            readonly token: string;
            readonly token_hint: string;
            readonly version: number;
        };
        BookingRequestApiCredentialRotateRequest: {
            confirm: boolean;
            version: number;
        };
        BookingRequestCounts: {
            new: number;
            processed: number;
            total: number;
        };
        BookingRequestListResponse: {
            booking_requests: components["schemas"]["BookingRequest"][];
            counts: components["schemas"]["BookingRequestCounts"];
            next_cursor: string | null;
        };
        BookingRequestProcessRequest: {
            version: number;
        };
        /**
         * @description * `NEW` - Нова
         *     * `PROCESSED` - Оброблена
         * @enum {string}
         */
        BookingRequestStatusEnum: "NEW" | "PROCESSED";
        /**
         * @description * `day` - day
         *     * `week` - week
         *     * `month` - month
         * @enum {string}
         */
        BucketEnum: "day" | "week" | "month";
        CalendarBreak: {
            /** Format: date-time */
            ends_at: string;
            /** Format: date-time */
            starts_at: string;
        };
        CalendarDay: {
            breaks: components["schemas"]["CalendarBreak"][];
            /** Format: date */
            date: string;
            /** Format: date-time */
            ends_at: string | null;
            is_working: boolean;
            /** Format: date-time */
            starts_at: string | null;
        };
        CalendarEvent: {
            duration_minutes: number;
            /** Format: date-time */
            ends_at: string;
            /** Format: uuid */
            id: string;
            patient: components["schemas"]["CalendarPatient"];
            public_number: string;
            room: components["schemas"]["RoomSummary"];
            service: components["schemas"]["CalendarService"];
            specialist: components["schemas"]["SpecialistSummary"];
            /** Format: date-time */
            starts_at: string;
            status: components["schemas"]["CalendarStatus"];
        };
        CalendarPatient: {
            display_name: string;
            /** Format: uuid */
            id: string;
            public_number: string;
        };
        CalendarRange: {
            /** Format: date-time */
            from: string;
            /** Format: date-time */
            to: string;
        };
        CalendarResponse: {
            days: components["schemas"]["CalendarDay"][];
            events: components["schemas"]["CalendarEvent"][];
            range: components["schemas"]["CalendarRange"];
            specialists: components["schemas"]["SpecialistSummary"][];
            timezone: string;
        };
        CalendarService: {
            color: string;
            /** Format: uuid */
            id: string;
            name: string;
        };
        CalendarStatus: {
            code: string;
            color: string;
            label: string;
        };
        /** @enum {boolean} */
        CashCountConfirmedEnum: true;
        CashLedgerEntry: {
            /** Format: email */
            actor_email: string;
            actor_id: number;
            actor_name: string;
            amount_minor: number;
            /** Format: uuid */
            id: string;
            kind: components["schemas"]["CashLedgerEntryKindEnum"];
            payment_method: (components["schemas"]["PaymentMethodEnum"] | components["schemas"]["NullEnum"]) | null;
            /** Format: date-time */
            posted_at: string;
            public_number: string;
        };
        /**
         * @description * `PAYMENT` - Оплата
         *     * `REFUND` - Повернення
         *     * `DEPOSIT` - Внесення
         *     * `WITHDRAWAL` - Вилучення
         * @enum {string}
         */
        CashLedgerEntryKindEnum: "PAYMENT" | "REFUND" | "DEPOSIT" | "WITHDRAWAL";
        CashMovementCreateRequest: {
            /** Format: int64 */
            amount_minor: number;
            /** @default  */
            comment: string;
            reason: string;
            type: components["schemas"]["CashMovementTypeEnum"];
        };
        CashMovementCreateResponse: {
            operation: components["schemas"]["FinanceCashAdjustmentOperation"];
            replayed: boolean;
        };
        /**
         * @description * `DEPOSIT` - DEPOSIT
         *     * `WITHDRAWAL` - WITHDRAWAL
         * @enum {string}
         */
        CashMovementTypeEnum: "DEPOSIT" | "WITHDRAWAL";
        CashShiftClosePreviewResponse: {
            shift: components["schemas"]["CashShiftProjection"];
            unpaid: components["schemas"]["CashShiftUnpaid"];
        };
        CashShiftCloseRequest: {
            /** Format: int64 */
            actual_cash_minor: number;
            cash_count_confirmed: components["schemas"]["CashCountConfirmedEnum"];
            /** @default  */
            comment: string;
            expected_operations_count: number;
        };
        CashShiftCloseResponse: {
            replayed: boolean;
            shift: components["schemas"]["CashShiftProjection"];
        };
        CashShiftCurrentResponse: {
            shift: components["schemas"]["CashShiftProjection"] | null;
        };
        CashShiftEmployee: {
            /** Format: email */
            email: string;
            id: number;
            name: string;
            role: components["schemas"]["RoleEnum"];
        };
        CashShiftListResponse: {
            next_cursor: string | null;
            shifts: components["schemas"]["CashShiftSummary"][];
        };
        CashShiftProjection: {
            /** Format: date-time */
            closed_at: string | null;
            employee: components["schemas"]["CashShiftEmployee"];
            entries: components["schemas"]["CashLedgerEntry"][];
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            opened_at: string;
            public_number: string;
            reconciliation: components["schemas"]["CashShiftReconciliation"] | null;
            status: components["schemas"]["CashShiftStatusEnum"];
            totals: components["schemas"]["CashShiftTotals"];
        };
        CashShiftReconciliation: {
            actual_cash_minor: number;
            closed_by: components["schemas"]["CashShiftEmployee"];
            comment: string;
            discrepancy_minor: number;
            expected_cash_minor: number;
        };
        /**
         * @description * `OPEN` - Відкрита
         *     * `CLOSED` - Закрита
         * @enum {string}
         */
        CashShiftStatusEnum: "OPEN" | "CLOSED";
        CashShiftSummary: {
            /** Format: date-time */
            closed_at: string | null;
            employee: components["schemas"]["CashShiftEmployee"];
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            opened_at: string;
            public_number: string;
            reconciliation: components["schemas"]["CashShiftReconciliation"] | null;
            status: components["schemas"]["CashShiftStatusEnum"];
            totals: components["schemas"]["CashShiftTotals"];
        };
        CashShiftTotals: {
            card_payments_minor: number;
            card_refunds_minor: number;
            cash_payments_minor: number;
            cash_refunds_minor: number;
            deposits_minor: number;
            expected_cash_minor: number;
            operations_count: number;
            payment_count: number;
            payments_total_minor: number;
            refund_count: number;
            refunds_total_minor: number;
            revenue_minor: number;
            transfer_payments_minor: number;
            transfer_refunds_minor: number;
            withdrawals_minor: number;
        };
        CashShiftUnpaid: {
            count: number;
            total_minor: number;
        };
        ChangePasswordRequestRequest: {
            current_password: string;
            new_password: string;
            new_password_confirmation: string;
        };
        ClinicBreak: {
            /** Format: time */
            end_time: string;
            /** Format: uuid */
            readonly id: string;
            /** Format: time */
            start_time: string;
        };
        ClinicBreakWriteRequest: {
            /** Format: time */
            end_time: string;
            /** Format: time */
            start_time: string;
        };
        ClinicLogoUploadRequest: {
            /** Format: binary */
            logo: string;
            version: number;
        };
        ClinicProfile: {
            address: string;
            description?: string;
            /** Format: email */
            email: string;
            readonly has_logo: boolean;
            logo_content_type?: string;
            logo_size?: number | null;
            readonly logo_url: string | null;
            name: string;
            phone: string;
            /** Format: date-time */
            readonly updated_at: string;
            version?: number;
        };
        ClinicScheduleUpdateRequest: {
            workdays: components["schemas"]["ClinicWorkdayWriteRequest"][];
        };
        ClinicWorkday: {
            breaks: components["schemas"]["ClinicBreak"][];
            /** Format: time */
            end_time: string | null;
            is_working?: boolean;
            /** Format: time */
            start_time: string | null;
            /** Format: date-time */
            readonly updated_at: string;
            version?: number;
            weekday: number;
        };
        ClinicWorkdayList: {
            timezone: string;
            workdays: components["schemas"]["ClinicWorkday"][];
        };
        ClinicWorkdayWriteRequest: {
            breaks?: components["schemas"]["ClinicBreakWriteRequest"][];
            /** Format: time */
            end_time?: string | null;
            is_working: boolean;
            /** Format: time */
            start_time?: string | null;
            version: number;
            weekday: number;
        };
        ContractFixture: {
            correlation_id: string;
            message: string;
            status: components["schemas"]["ContractFixtureStatusEnum"];
        };
        /**
         * @description * `ok` - ok
         * @enum {string}
         */
        ContractFixtureStatusEnum: "ok";
        /**
         * @description * `HYPERKERATOSIS` - Гіперкератоз
         *     * `FISSURES` - Тріщини
         *     * `NAIL_DEFORMATION` - Деформація нігтя
         *     * `REDNESS` - Почервоніння
         *     * `EDEMA` - Набряк
         *     * `TENDERNESS` - Болісність
         * @enum {string}
         */
        DetectedConditionEnum: "HYPERKERATOSIS" | "FISSURES" | "NAIL_DEFORMATION" | "REDNESS" | "EDEMA" | "TENDERNESS";
        /**
         * @description * `MATCH` - Без різниці
         *     * `SURPLUS` - Надлишок
         *     * `SHORTAGE` - Нестача
         * @enum {string}
         */
        DifferenceKindEnum: "MATCH" | "SURPLUS" | "SHORTAGE";
        /**
         * @description * `own` - own
         *     * `all` - all
         * @enum {string}
         */
        EffectiveScopeEnum: "own" | "all";
        ErrorEnvelope: {
            code: string;
            correlation_id: string;
            fields: {
                [key: string]: string[];
            };
            message: string;
        };
        ExternalBookingRequestRequest: {
            /** @default  */
            client_name: string;
            /** @default  */
            contact_handle: string;
            /** @default  */
            external_reference: string;
            /** @default  */
            message: string;
            /** @default  */
            phone: string;
            /** Format: date-time */
            preferred_at?: string | null;
            /** @default  */
            service: string;
            source: components["schemas"]["SourceEnum"];
        };
        ExternalBookingRequestResponse: {
            /** Format: date-time */
            readonly created_at: string;
            /** Format: uuid */
            readonly id: string;
            readonly public_number: string;
            status?: components["schemas"]["BookingRequestStatusEnum"];
        };
        FinanceCashAdjustment: {
            actor: components["schemas"]["FinancePaymentActor"];
            cash_shift: components["schemas"]["FinancePaymentShift"];
            comment: string;
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            ledger_entry_id: string;
            /** Format: date-time */
            posted_at: string;
            public_number: string;
            reason: string;
        };
        FinanceCashAdjustmentOperation: {
            amount_minor: number;
            cash_adjustment: components["schemas"]["FinanceCashAdjustment"];
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            occurred_at: string;
            status: components["schemas"]["PostedFinanceStatusEnum"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "DEPOSIT" | "WITHDRAWAL";
        };
        FinanceOperation: components["schemas"]["FinancePaymentOperation"] | components["schemas"]["FinanceRefundOperation"] | components["schemas"]["FinanceCashAdjustmentOperation"];
        FinanceOperationListResponse: {
            next_cursor: string | null;
            operations: components["schemas"]["FinanceOperation"][];
        };
        FinancePatient: {
            display_name: string;
            /** Format: uuid */
            id: string;
            phone: string;
            public_number: string;
        };
        FinancePayment: {
            actor: components["schemas"]["FinancePaymentActor"];
            cash_shift: components["schemas"]["FinancePaymentShift"];
            comment: string;
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            ledger_entry_id: string;
            payment_method: components["schemas"]["PaymentMethodEnum"];
            /** Format: date-time */
            posted_at: string;
            public_number: string;
        };
        FinancePaymentActor: {
            id: number;
            name: string;
        };
        FinancePaymentOperation: {
            amount_minor: number;
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            occurred_at: string;
            patient: components["schemas"]["FinancePatient"];
            payment: components["schemas"]["FinancePayment"] | null;
            refund: components["schemas"]["FinanceRefund"] | null;
            status: components["schemas"]["ReceivableStatusEnum"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "PAYMENT";
            visit: components["schemas"]["FinanceVisit"];
        };
        /**
         * @description * `PAYMENT` - PAYMENT
         * @enum {string}
         */
        FinancePaymentOperationTypeEnum: "PAYMENT";
        FinancePaymentShift: {
            /** Format: uuid */
            id: string;
            public_number: string;
        };
        FinanceRefund: {
            actor: components["schemas"]["FinancePaymentActor"];
            cash_shift: components["schemas"]["FinancePaymentShift"];
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            ledger_entry_id: string;
            /** Format: date-time */
            posted_at: string;
            public_number: string;
            reason: string;
        };
        FinanceRefundOperation: {
            amount_minor: number;
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            occurred_at: string;
            original_payment: components["schemas"]["FinancePayment"];
            patient: components["schemas"]["FinancePatient"];
            refund: components["schemas"]["FinanceRefund"];
            status: components["schemas"]["PostedFinanceStatusEnum"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "REFUND";
            visit: components["schemas"]["FinanceVisit"];
        };
        /**
         * @description * `REFUND` - REFUND
         * @enum {string}
         */
        FinanceRefundOperationTypeEnum: "REFUND";
        FinanceService: {
            code: string;
            /** Format: uuid */
            id: string;
            line_total_minor: number;
            name: string;
            quantity: number;
            unit_price_minor: number;
        };
        FinanceSpecialist: {
            id: number;
            name: string;
        };
        FinanceVisit: {
            /** Format: date-time */
            completed_at: string;
            /** Format: uuid */
            id: string;
            payment_handoff_requested: boolean;
            public_number: string;
            services: components["schemas"]["FinanceService"][];
            specialist: components["schemas"]["FinanceSpecialist"];
            total_minor: number;
        };
        /**
         * @description * `integer` - integer
         *     * `money` - money
         *     * `duration` - duration
         * @enum {string}
         */
        FormatEnum: "integer" | "money" | "duration";
        GlobalSearchGroup: {
            has_more: boolean;
            items: components["schemas"]["GlobalSearchItem"][];
            type: components["schemas"]["GlobalSearchGroupTypeEnum"];
        };
        /**
         * @description * `patients` - patients
         *     * `appointments` - appointments
         *     * `payments` - payments
         *     * `materials` - materials
         * @enum {string}
         */
        GlobalSearchGroupTypeEnum: "patients" | "appointments" | "payments" | "materials";
        GlobalSearchItem: {
            deep_link: string;
            /** Format: uuid */
            id: string;
            meta: string;
            subtitle: string;
            title: string;
            type: components["schemas"]["GlobalSearchItemTypeEnum"];
        };
        /**
         * @description * `patient` - patient
         *     * `appointment` - appointment
         *     * `payment` - payment
         *     * `material` - material
         * @enum {string}
         */
        GlobalSearchItemTypeEnum: "patient" | "appointment" | "payment" | "material";
        GlobalSearchResponse: {
            groups: components["schemas"]["GlobalSearchGroup"][];
            query: string;
            returned_count: number;
        };
        InventoryOperation: {
            comment?: string;
            /** Format: email */
            readonly created_by_email: string;
            readonly created_by_id: number;
            readonly created_by_name: string;
            /** Format: uuid */
            readonly id: string;
            kind: components["schemas"]["InventoryOperationKindEnum"];
            readonly movement_count: number;
            readonly movements: components["schemas"]["StockMovement"][];
            /** Format: date-time */
            readonly posted_at: string;
            readonly public_number: string;
            reason?: string;
            readonly replayed: boolean;
            readonly status: string;
        };
        /**
         * @description * `RECEIPT` - Надходження
         *     * `VISIT_USAGE` - Використання у прийомі
         *     * `MANUAL_WRITEOFF` - Ручне списання
         *     * `STOCKTAKE_ADJUSTMENT` - Коригування інвентаризації
         * @enum {string}
         */
        InventoryOperationKindEnum: "RECEIPT" | "VISIT_USAGE" | "MANUAL_WRITEOFF" | "STOCKTAKE_ADJUSTMENT";
        LoginRequestRequest: {
            email: string;
            password: string;
        };
        ManualWriteoffCreateRequest: {
            /** @default  */
            comment: string;
            lines: components["schemas"]["ManualWriteoffLineRequest"][];
            reason: string;
        };
        ManualWriteoffLineRequest: {
            /** Format: uuid */
            lot_id: string;
            /** Format: decimal */
            quantity: string;
        };
        Material: {
            /** Format: decimal */
            readonly available_quantity: string;
            category: string;
            /** Format: date-time */
            readonly created_at: string;
            /** Format: uuid */
            readonly id: string;
            is_active?: boolean;
            readonly lots_count: number;
            /** Format: decimal */
            minimum_quantity?: string;
            name: string;
            /** Format: date */
            readonly nearest_expiry: string | null;
            sku: string;
            readonly stock_status: components["schemas"]["StockStatusEnum"];
            /** Format: decimal */
            readonly total_quantity: string;
            unit: string;
            /** Format: date-time */
            readonly updated_at: string;
            version?: number;
        };
        MaterialCreateRequest: {
            category: string;
            /** @default true */
            is_active: boolean;
            /** Format: decimal */
            minimum_quantity: string;
            name: string;
            sku: string;
            unit: string;
        };
        MaterialList: {
            materials: components["schemas"]["Material"][];
        };
        MaterialLot: {
            /** Format: date-time */
            readonly created_at: string;
            /** Format: decimal */
            current_quantity: string;
            /** Format: date */
            expires_on?: string | null;
            readonly fefo_rank: number | null;
            /** Format: uuid */
            readonly id: string;
            /** Format: decimal */
            initial_quantity: string;
            readonly is_expired: boolean;
            readonly is_usable: boolean;
            lot_number: string;
            /** Format: int64 */
            purchase_price_minor?: number | null;
            /** Format: date */
            received_on: string;
            readonly status: string;
            /** Format: uuid */
            readonly supplier_id: string | null;
            supplier_name?: string;
        };
        MaterialLotList: {
            lots: components["schemas"]["MaterialLot"][];
        };
        MedicalPatientDetail: {
            readonly age: number | null;
            readonly appointment_summary: unknown;
            /** Format: date */
            birth_date?: string | null;
            /** Format: date-time */
            readonly created_at: string;
            readonly display_name: string;
            email?: string;
            first_name: string;
            /** Format: uuid */
            readonly id: string;
            last_name: string;
            readonly medical_profile: components["schemas"]["PatientMedicalProfile"];
            note?: string;
            phone: string;
            readonly photo_archive: components["schemas"]["PatientPhotoVisitMetadata"][];
            readonly primary_podologist: components["schemas"]["PodologistSummary"] | null;
            readonly projection: string;
            readonly public_number: string;
            /** Format: date-time */
            readonly service_started_at: string;
            readonly state_label: string;
            readonly upcoming_appointment: components["schemas"]["PatientAppointmentSummary"] | null;
            /** Format: date-time */
            readonly updated_at: string;
            readonly visit_history: components["schemas"]["PatientHistoryMedicalItem"][];
        };
        MovementJournalItem: {
            /** Format: email */
            readonly actor_email: string;
            readonly actor_id: number;
            readonly actor_name: string;
            /** Format: decimal */
            balance_after: string;
            /** Format: date-time */
            readonly created_at: string;
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            readonly lot_id: string;
            readonly lot_number: string;
            /** Format: uuid */
            readonly material_id: string;
            readonly material_name: string;
            readonly material_sku: string;
            readonly material_unit: string;
            readonly operation_comment: string;
            /** Format: uuid */
            readonly operation_id: string;
            readonly operation_kind: components["schemas"]["InventoryOperationKindEnum"];
            readonly operation_public_number: string;
            readonly operation_reason: string;
            /** Format: date-time */
            readonly posted_at: string;
            /** Format: decimal */
            quantity_delta: string;
        };
        MovementJournalResponse: {
            movements: components["schemas"]["MovementJournalItem"][];
            next_cursor: string | null;
        };
        Notification: {
            /** Format: date-time */
            created_at: string;
            deep_link: string;
            /** Format: uuid */
            id: string;
            is_important: boolean;
            is_read: boolean;
            kind: components["schemas"]["NotificationKindEnum"];
            message: string;
            /** Format: date-time */
            occurred_at: string;
            /** Format: date-time */
            read_at: string | null;
            title: string;
            tone: components["schemas"]["NotificationToneEnum"];
        };
        /**
         * @description * `appointment_arrived` - Пацієнт прибув
         *     * `appointment_upcoming` - Запис незабаром
         *     * `appointment_canceled` - Запис скасовано
         *     * `work_item_overdue` - Справу прострочено
         *     * `visit_payment_ready` - Прийом очікує оплати
         *     * `password_reset_requested` - Запит на скидання пароля
         * @enum {string}
         */
        NotificationKindEnum: "appointment_arrived" | "appointment_upcoming" | "appointment_canceled" | "work_item_overdue" | "visit_payment_ready" | "password_reset_requested";
        NotificationListResponse: {
            next_cursor: string | null;
            notifications: components["schemas"]["Notification"][];
            total_count: number;
            unread_count: number;
        };
        NotificationMarkAllResponse: {
            marked_count: number;
            unread_count: number;
        };
        /**
         * @description * `sage` - Зелений
         *     * `sand` - Пісочний
         *     * `blue` - Синій
         *     * `lilac` - Ліловий
         *     * `coral` - Кораловий
         * @enum {string}
         */
        NotificationToneEnum: "sage" | "sand" | "blue" | "lilac" | "coral";
        /** @enum {unknown} */
        NullEnum: null;
        OverviewAppointment: {
            duration_minutes: number;
            /** Format: date-time */
            ends_at: string;
            /** Format: uuid */
            id: string;
            patient: components["schemas"]["OverviewPatient"];
            public_number: string;
            room: components["schemas"]["OverviewResource"];
            service: components["schemas"]["OverviewService"];
            specialist: components["schemas"]["OverviewSpecialist"];
            /** Format: date-time */
            starts_at: string;
            status: components["schemas"]["OverviewStatus"];
        };
        OverviewAttention: {
            count: number;
            deep_link: string;
            kind: string;
            label: string;
        };
        OverviewMetric: {
            format: components["schemas"]["FormatEnum"];
            key: string;
            label: string;
            note: string;
            tone: components["schemas"]["OverviewMetricToneEnum"];
            value: number;
        };
        /**
         * @description * `sage` - sage
         *     * `sand` - sand
         *     * `lilac` - lilac
         *     * `coral` - coral
         *     * `blue` - blue
         * @enum {string}
         */
        OverviewMetricToneEnum: "sage" | "sand" | "lilac" | "coral" | "blue";
        OverviewPatient: {
            display_name: string;
            /** Format: uuid */
            id: string;
            public_number: string;
        };
        OverviewResource: {
            /** Format: uuid */
            id: string;
            name: string;
        };
        OverviewResponse: {
            attention: components["schemas"]["OverviewAttention"][];
            /** Format: date */
            date: string;
            metrics: components["schemas"]["OverviewMetric"][];
            next_appointment: components["schemas"]["OverviewAppointment"] | null;
            role: string;
            schedule: components["schemas"]["OverviewAppointment"][];
            timezone: string;
            workday: components["schemas"]["OverviewWorkday"];
        };
        OverviewService: {
            color: string;
            /** Format: uuid */
            id: string;
            name: string;
        };
        OverviewSpecialist: {
            display_name: string;
            id: number;
        };
        OverviewStatus: {
            code: string;
            color: string;
            label: string;
        };
        OverviewWorkday: {
            break_minutes: number;
            /** Format: date-time */
            ends_at: string | null;
            is_working: boolean;
            net_minutes: number;
            /** Format: date-time */
            starts_at: string | null;
        };
        PasswordPairRequest: {
            new_password: string;
            new_password_confirmation: string;
        };
        PasswordResetRequestAccepted: {
            message: string;
        };
        PasswordResetRequestCreateRequest: {
            /** Format: email */
            email: string;
        };
        PasswordResetRequestItem: {
            id: number;
            /** Format: date-time */
            requested_at: string;
            user: components["schemas"]["PasswordResetRequestUser"];
        };
        PasswordResetRequestList: {
            requests: components["schemas"]["PasswordResetRequestItem"][];
        };
        PasswordResetRequestUser: {
            display_name: string;
            /** Format: email */
            email: string;
            id: number;
            role: components["schemas"]["RoleEnum"];
        };
        PatchedAppointmentStatusConfigUpdateRequest: {
            color?: string;
            label?: string;
            manual_admin?: boolean;
            manual_podologist?: boolean;
            manual_reception?: boolean;
            version?: number;
        };
        PatchedClinicProfileUpdateRequest: {
            address?: string;
            description?: string;
            /** Format: email */
            email?: string;
            name?: string;
            phone?: string;
            version?: number;
        };
        PatchedMaterialUpdateRequest: {
            category?: string;
            is_active?: boolean;
            /** Format: decimal */
            minimum_quantity?: string;
            name?: string;
            sku?: string;
            unit?: string;
            version?: number;
        };
        PatchedMedicalPatientUpdateRequest: {
            /** Format: date */
            birth_date?: string | null;
            email?: string;
            first_name?: string;
            last_name?: string;
            medical_profile?: components["schemas"]["PatientMedicalProfileUpdateRequest"];
            note?: string;
            phone?: string;
            primary_podologist_id?: number | null;
        };
        PatchedPatientUpdateRequestRequest: components["schemas"]["PatchedReceptionPatientUpdateRequest"] | components["schemas"]["PatchedMedicalPatientUpdateRequest"];
        PatchedReceptionPatientUpdateRequest: {
            /** Format: date */
            birth_date?: string | null;
            email?: string;
            first_name?: string;
            last_name?: string;
            note?: string;
            phone?: string;
            primary_podologist_id?: number | null;
        };
        PatchedRoomUpdateRequest: {
            is_active?: boolean;
            name?: string;
            version?: number;
        };
        PatchedServiceUpdateRequest: {
            code?: string;
            color?: string;
            duration_minutes?: number;
            is_active?: boolean;
            name?: string;
            price_minor?: number;
            version?: number;
        };
        PatchedSupplierUpdateRequest: {
            address?: string;
            contact_name?: string;
            email?: string;
            is_active?: boolean;
            name?: string;
            note?: string;
            phone?: string;
            version?: number;
        };
        PatchedTeamUserUpdateRequest: {
            /** Format: email */
            email?: string;
            first_name?: string;
            is_active?: boolean;
            last_name?: string;
            phone?: string;
            role?: components["schemas"]["RoleEnum"];
        };
        PatchedVisitRecommendationUpdateRequest: {
            text?: string;
            version?: number;
        };
        PatchedWorkItemUpdateRequest: {
            assignee_id?: number;
            comment?: string;
            /** Format: date-time */
            due_at?: string;
            is_completed?: boolean;
            is_important?: boolean;
            kind?: components["schemas"]["WorkItemKindEnum"];
            /** Format: uuid */
            patient_id?: string | null;
            title?: string;
            version: number;
        };
        Patient: {
            readonly appointment_summary: unknown;
            /** Format: date */
            birth_date?: string | null;
            /** Format: date-time */
            readonly created_at: string;
            readonly display_name: string;
            email?: string;
            first_name: string;
            /** Format: uuid */
            readonly id: string;
            last_name: string;
            note?: string;
            phone: string;
            readonly primary_podologist: components["schemas"]["PodologistSummary"] | null;
            readonly public_number: string;
            readonly state_label: string;
            /** Format: date-time */
            readonly updated_at: string;
        };
        PatientAppointmentSummary: {
            cost_minor: number;
            room: string;
            service: string;
            specialist: string;
            /** Format: date-time */
            starts_at: string;
            status: string;
        };
        PatientCreateRequest: {
            /** Format: date */
            birth_date?: string | null;
            email?: string;
            first_name: string;
            last_name: string;
            note?: string;
            phone: string;
            primary_podologist_id?: number | null;
        };
        PatientCreateResponse: {
            duplicate_warning: boolean;
            patient: components["schemas"]["Patient"];
            possible_duplicates: components["schemas"]["PatientListItem"][];
        };
        PatientDetailResponse: components["schemas"]["ReceptionPatientDetail"] | components["schemas"]["MedicalPatientDetail"];
        PatientHistoryBaseItem: {
            /** Format: date-time */
            completed_at: string;
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            occurred_at: string;
            public_number: string;
            services: components["schemas"]["PatientHistoryService"][];
            specialist: components["schemas"]["PatientHistorySpecialist"];
            status: string;
            status_label: string;
            total_minor: number;
        };
        PatientHistoryMedicalItem: {
            after_photo_count: number;
            before_photo_count: number;
            clinical_summary: string;
            /** Format: date-time */
            completed_at: string;
            has_photos: boolean;
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            occurred_at: string;
            public_number: string;
            recommendations_count: number;
            services: components["schemas"]["PatientHistoryService"][];
            specialist: components["schemas"]["PatientHistorySpecialist"];
            status: string;
            status_label: string;
            total_minor: number;
        };
        PatientHistoryMedicalResponse: {
            next_cursor: string | null;
            visits: components["schemas"]["PatientHistoryMedicalItem"][];
        };
        PatientHistoryResponse: components["schemas"]["PatientHistorySafeResponse"] | components["schemas"]["PatientHistoryMedicalResponse"];
        PatientHistorySafeResponse: {
            next_cursor: string | null;
            visits: components["schemas"]["PatientHistoryBaseItem"][];
        };
        PatientHistoryService: {
            line_total_minor: number;
            quantity: number;
            service_name: string;
        };
        PatientHistorySpecialist: {
            display_name: string;
            id: number;
        };
        PatientListItem: {
            readonly appointment_summary: unknown;
            /** Format: date */
            birth_date?: string | null;
            /** Format: date-time */
            readonly created_at: string;
            readonly display_name: string;
            email?: string;
            first_name: string;
            /** Format: uuid */
            readonly id: string;
            last_name: string;
            phone: string;
            readonly primary_podologist: components["schemas"]["PodologistSummary"] | null;
            readonly public_number: string;
            readonly state_label: string;
        };
        PatientListResponse: {
            next_cursor: string | null;
            patients: components["schemas"]["PatientListItem"][];
        };
        PatientMedicalProfile: {
            allergies?: unknown;
            chronic_conditions?: unknown;
            notes?: string;
            /** Format: date-time */
            readonly updated_at: string;
        };
        PatientMedicalProfileUpdateRequest: {
            allergies?: string[];
            chronic_conditions?: string[];
            notes?: string;
        };
        PatientPhotoArchiveResponse: {
            next_cursor: string | null;
            visits: components["schemas"]["PatientPhotoArchiveVisit"][];
        };
        PatientPhotoArchiveVisit: {
            /** Format: date-time */
            completed_at: string;
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            occurred_at: string;
            photos: components["schemas"]["VisitPhoto"][];
            public_number: string;
            services: components["schemas"]["PatientHistoryService"][];
            specialist: components["schemas"]["PatientHistorySpecialist"];
            status: string;
            status_label: string;
            total_minor: number;
        };
        PatientPhotoVisitMetadata: {
            after_count: number;
            before_count: number;
            caption: string;
            /** Format: date-time */
            occurred_at: string;
            /** Format: uuid */
            visit_id: string;
        };
        PatientRecommendation: {
            author: components["schemas"]["RecommendationAuthor"];
            can_edit: boolean;
            /** Format: date-time */
            created_at: string;
            /** Format: uuid */
            id: string;
            text: string;
            /** Format: date-time */
            updated_at: string;
            version: number;
            visit: components["schemas"]["RecommendationVisitSummary"];
        };
        PatientRecommendationResponse: {
            eligible_visits: components["schemas"]["RecommendationVisitSummary"][];
            next_cursor: string | null;
            recommendations: components["schemas"]["PatientRecommendation"][];
        };
        PaymentCreateRequest: {
            /** @default  */
            comment: string;
            payment_method: components["schemas"]["PaymentMethodEnum"];
            /** Format: uuid */
            visit_id: string;
        };
        PaymentCreateResponse: {
            operation: components["schemas"]["FinancePaymentOperation"];
            replayed: boolean;
        };
        /**
         * @description * `CASH` - Готівка
         *     * `CARD` - Картка
         *     * `TRANSFER` - Переказ
         * @enum {string}
         */
        PaymentMethodEnum: "CASH" | "CARD" | "TRANSFER";
        PodologistSummary: {
            readonly display_name: string;
            readonly id: number;
        };
        /**
         * @description * `POSTED` - POSTED
         * @enum {string}
         */
        PostedFinanceStatusEnum: "POSTED";
        ReceiptCreateRequest: {
            /** @default  */
            comment: string;
            lines: components["schemas"]["ReceiptLineRequest"][];
            /** Format: date */
            received_on?: string;
        };
        ReceiptLineRequest: {
            /** @default false */
            allow_existing_lot: boolean;
            /** Format: date */
            expires_on?: string | null;
            lot_number: string;
            /** Format: uuid */
            material_id: string;
            purchase_price_minor?: number | null;
            /** Format: decimal */
            quantity: string;
            /** Format: uuid */
            supplier_id?: string | null;
            /** @default  */
            supplier_name: string;
        };
        /**
         * @description * `OPEN` - Очікує оплати
         *     * `PAID` - Оплачено
         *     * `REFUNDED` - Повернено
         * @enum {string}
         */
        ReceivableStatusEnum: "OPEN" | "PAID" | "REFUNDED";
        /** @description Safe contact/administrative projection with no medical keys. */
        ReceptionPatientDetail: {
            readonly age: number | null;
            readonly appointment_summary: unknown;
            /** Format: date */
            birth_date?: string | null;
            /** Format: date-time */
            readonly created_at: string;
            readonly display_name: string;
            email?: string;
            first_name: string;
            /** Format: uuid */
            readonly id: string;
            last_name: string;
            note?: string;
            phone: string;
            readonly primary_podologist: components["schemas"]["PodologistSummary"] | null;
            readonly projection: string;
            readonly public_number: string;
            /** Format: date-time */
            readonly service_started_at: string;
            readonly state_label: string;
            readonly upcoming_appointment: components["schemas"]["PatientAppointmentSummary"] | null;
            /** Format: date-time */
            readonly updated_at: string;
            readonly visit_history: components["schemas"]["PatientHistoryBaseItem"][];
        };
        RecommendationAuthor: {
            display_name: string;
            id: number;
        };
        RecommendationVisitSummary: {
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            occurred_at: string;
            public_number: string;
            services: string[];
        };
        RefundCreateRequest: {
            reason: string;
        };
        RefundCreateResponse: {
            operation: components["schemas"]["FinanceRefundOperation"];
            replayed: boolean;
        };
        /**
         * @description * `podologist` - Подолог
         *     * `reception` - Рецепція
         *     * `admin` - Адміністратор
         * @enum {string}
         */
        RoleEnum: "podologist" | "reception" | "admin";
        Room: {
            /** Format: date-time */
            readonly created_at: string;
            /** Format: uuid */
            readonly id: string;
            is_active?: boolean;
            name: string;
            /** Format: date-time */
            readonly updated_at: string;
            version?: number;
        };
        RoomCreateRequest: {
            /** @default true */
            is_active: boolean;
            name: string;
        };
        RoomList: {
            rooms: components["schemas"]["Room"][];
        };
        RoomSummary: {
            /** Format: uuid */
            id: string;
            name: string;
        };
        Service: {
            code: string;
            color?: string;
            /** Format: date-time */
            readonly created_at: string;
            duration_minutes: number;
            /** Format: uuid */
            readonly id: string;
            is_active?: boolean;
            name: string;
            /** Format: int64 */
            price_minor: number;
            /** Format: date-time */
            readonly updated_at: string;
            version?: number;
        };
        ServiceCreateRequest: {
            code: string;
            color: string;
            duration_minutes: number;
            /** @default true */
            is_active: boolean;
            name: string;
            price_minor: number;
        };
        ServiceList: {
            services: components["schemas"]["Service"][];
        };
        Session: {
            must_change_password: boolean;
            notification_unread_count: number;
            route_ids: string[];
            temporary_password_expired: boolean;
            /** Format: date-time */
            temporary_password_expires_at: string | null;
            user: components["schemas"]["SessionUser"];
        };
        SessionUser: {
            display_name: string;
            /** Format: email */
            email: string;
            id: number;
            role: components["schemas"]["RoleEnum"];
        };
        /**
         * @description * `INSTAGRAM` - Instagram
         *     * `FACEBOOK` - Facebook
         *     * `WEBSITE` - Сайт
         * @enum {string}
         */
        SourceEnum: "INSTAGRAM" | "FACEBOOK" | "WEBSITE";
        SpecialistSummary: {
            display_name: string;
            id: number;
        };
        StartVisitRequest: {
            version: number;
        };
        StockMovement: {
            /** Format: decimal */
            balance_after: string;
            /** Format: date-time */
            readonly created_at: string;
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            readonly lot_id: string;
            readonly lot_number: string;
            /** Format: uuid */
            readonly material_id: string;
            readonly material_name: string;
            readonly material_unit: string;
            /** Format: decimal */
            quantity_delta: string;
            /** Format: uuid */
            readonly supplier_id: string | null;
            readonly supplier_name: string;
        };
        /**
         * @description * `out_of_stock` - Немає в наявності
         *     * `low` - Низький залишок
         *     * `expired` - Є прострочена партія
         *     * `expiring` - Закінчується термін
         *     * `healthy` - В наявності
         * @enum {string}
         */
        StockStatusEnum: "out_of_stock" | "low" | "expired" | "expiring" | "healthy";
        Stocktake: {
            readonly adjusted_line_count: number;
            readonly adjustment_value_minor: number;
            comment?: string;
            /** Format: date-time */
            readonly created_at: string;
            readonly created_by_id: number;
            readonly created_by_name: string;
            /** Format: uuid */
            readonly id: string;
            readonly line_count: number;
            readonly lines: components["schemas"]["StocktakeLine"][];
            /** Format: uuid */
            readonly operation_id: string | null;
            /** Format: date-time */
            readonly posted_at: string | null;
            readonly posted_by_id: number | null;
            readonly posted_by_name: string | null;
            readonly public_number: string;
            readonly replayed: boolean;
            readonly shortage_line_count: number;
            status?: components["schemas"]["StocktakeStatusEnum"];
            readonly surplus_line_count: number;
            readonly unpriced_adjustment_count: number;
        };
        StocktakeCreateLineRequest: {
            /** Format: decimal */
            actual_quantity: string;
            /** Format: uuid */
            lot_id: string;
        };
        StocktakeCreateRequest: {
            /** @default  */
            comment: string;
            lines: components["schemas"]["StocktakeCreateLineRequest"][];
        };
        StocktakeLine: {
            /** Format: decimal */
            actual_quantity: string;
            readonly adjustment_value_minor: number | null;
            /** Format: decimal */
            readonly difference: string;
            readonly difference_kind: components["schemas"]["DifferenceKindEnum"];
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            readonly lot_id: string;
            readonly lot_number: string;
            readonly material_name: string;
            readonly material_sku: string;
            readonly material_unit: string;
            readonly purchase_price_minor: number | null;
            /** Format: decimal */
            readonly system_quantity: string;
        };
        StocktakePreview: {
            lots: components["schemas"]["StocktakePreviewLot"][];
        };
        StocktakePreviewLot: {
            /** Format: date */
            expires_on?: string | null;
            /** Format: uuid */
            readonly id: string;
            readonly is_expired: boolean;
            lot_number: string;
            /** Format: uuid */
            readonly material_id: string;
            readonly material_name: string;
            readonly material_sku: string;
            readonly material_unit: string;
            /** Format: int64 */
            purchase_price_minor?: number | null;
            /** Format: decimal */
            readonly system_quantity: string;
        };
        /**
         * @description * `DRAFT` - Чернетка
         *     * `POSTED` - Проведено
         * @enum {string}
         */
        StocktakeStatusEnum: "DRAFT" | "POSTED";
        Supplier: {
            address?: string;
            contact_name?: string;
            /** Format: date-time */
            readonly created_at: string;
            email?: string;
            /** Format: uuid */
            readonly id: string;
            is_active?: boolean;
            readonly lots_count: number;
            name: string;
            note?: string;
            phone?: string;
            /** Format: date-time */
            readonly updated_at: string;
            version?: number;
        };
        SupplierCreateRequest: {
            /** @default  */
            address: string;
            /** @default  */
            contact_name: string;
            email?: string;
            /** @default true */
            is_active: boolean;
            name: string;
            /** @default  */
            note: string;
            /** @default  */
            phone: string;
        };
        SupplierList: {
            suppliers: components["schemas"]["Supplier"][];
        };
        TeamUser: {
            display_name: string;
            /** Format: email */
            email: string;
            first_name: string;
            id: number;
            is_active: boolean;
            /** Format: date-time */
            last_login: string | null;
            last_name: string;
            must_change_password: boolean;
            phone: string;
            role: components["schemas"]["RoleEnum"];
            /** Format: date-time */
            temporary_password_expires_at: string | null;
        };
        TeamUserCreateRequest: {
            /** Format: email */
            email: string;
            first_name: string;
            /** @default true */
            is_active: boolean;
            last_name: string;
            /** @default true */
            must_change_password: boolean;
            /** @default  */
            phone: string;
            role: components["schemas"]["RoleEnum"];
            temporary_password: string;
            temporary_password_confirmation: string;
        };
        TeamUserList: {
            users: components["schemas"]["TeamUser"][];
        };
        TelegramLinkIntent: {
            /** Format: date-time */
            expires_at: string;
            /** Format: uri */
            url: string;
        };
        TelegramSubscription: {
            /** Format: date-time */
            disabled_at?: string | null;
            first_name?: string;
            is_enabled?: boolean;
            readonly is_linked: boolean;
            /** Format: date-time */
            last_seen_at: string;
            /** Format: date-time */
            linked_at: string;
            username?: string;
        };
        TemporaryPasswordRequestRequest: {
            temporary_password: string;
            temporary_password_confirmation: string;
        };
        TemporaryPasswordResult: {
            must_change_password: boolean;
            /** Format: date-time */
            temporary_password_expires_at: string;
            user_id: number;
        };
        VisitAppointment: {
            /** Format: date-time */
            ends_at: string;
            /** Format: uuid */
            id: string;
            public_number: string;
            room_name: string;
            service_name: string;
            /** Format: date-time */
            starts_at: string;
            status_code: string;
            status_label: string;
        };
        VisitDraftUpdateRequest: {
            complaints?: string;
            detected_conditions?: components["schemas"]["DetectedConditionEnum"][];
            has_no_complaints?: boolean;
            material_lines?: components["schemas"]["VisitMaterialLineInputRequest"][];
            objective_examination?: string;
            podologist_notes?: string;
            service_lines?: components["schemas"]["VisitServiceLineInputRequest"][];
            version: number;
        };
        VisitFinishRequest: {
            follow_up?: components["schemas"]["VisitFollowUpInputRequest"] | null;
            payment_handoff_requested: boolean;
            /** @default  */
            recommendations: string;
            version: number;
        };
        VisitFinishResponse: {
            /** Format: uuid */
            follow_up_appointment_id: string | null;
            /** Format: uuid */
            inventory_operation_id: string | null;
            movement_ids: string[];
            receivable: components["schemas"]["VisitReceivable"];
            replayed: boolean;
            visit: components["schemas"]["VisitResponse"];
        };
        VisitFollowUpInputRequest: {
            /** Format: uuid */
            room_id: string;
            /** Format: uuid */
            service_id: string;
            specialist_id: number;
            /** Format: date-time */
            starts_at: string;
        };
        VisitMaterialLine: {
            /** Format: decimal */
            available_quantity: string;
            /** Format: date */
            expires_on: string | null;
            /** Format: uuid */
            id: string;
            is_available: boolean;
            /** Format: uuid */
            lot_id: string;
            lot_number: string;
            /** Format: uuid */
            material_id: string;
            material_name: string;
            material_sku: string;
            material_unit: string;
            /** Format: decimal */
            quantity: string;
        };
        VisitMaterialLineInputRequest: {
            /** Format: uuid */
            lot_id: string;
            /** Format: decimal */
            quantity: string;
        };
        VisitMaterialLotOption: {
            /** Format: decimal */
            current_quantity: string;
            /** Format: date */
            expires_on: string | null;
            fefo_rank: number;
            /** Format: uuid */
            id: string;
            lot_number: string;
        };
        VisitMaterialOption: {
            /** Format: decimal */
            available_quantity: string;
            /** Format: uuid */
            id: string;
            lots: components["schemas"]["VisitMaterialLotOption"][];
            name: string;
            sku: string;
            unit: string;
        };
        VisitMaterialOptionList: {
            materials: components["schemas"]["VisitMaterialOption"][];
        };
        VisitPatient: {
            display_name: string;
            /** Format: uuid */
            id: string;
            public_number: string;
        };
        VisitPhoto: {
            content_type: string;
            /** Format: date-time */
            created_at: string;
            created_by_id: number;
            created_by_name: string;
            height: number;
            /** Format: uuid */
            id: string;
            image_url: string;
            kind: components["schemas"]["VisitPhotoKindEnum"];
            original_name: string;
            preview_status: components["schemas"]["VisitPhotoPreviewStatusEnum"];
            preview_url: string | null;
            size: number;
            /** Format: uuid */
            visit_id: string;
            width: number;
        };
        VisitPhotoFinalizeRequest: {
            /** Format: uuid */
            intent_id: string;
            /** Format: binary */
            photo: string;
        };
        VisitPhotoIntentCreateRequest: {
            kind: components["schemas"]["VisitPhotoKindEnum"];
        };
        /**
         * @description * `BEFORE` - До процедури
         *     * `AFTER` - Після процедури
         * @enum {string}
         */
        VisitPhotoKindEnum: "BEFORE" | "AFTER";
        /**
         * @description * `PROCESSING` - Обробляється
         *     * `READY` - Готове
         *     * `FAILED` - Помилка
         * @enum {string}
         */
        VisitPhotoPreviewStatusEnum: "PROCESSING" | "READY" | "FAILED";
        VisitPhotoUploadIntent: {
            allowed_content_types: string[];
            /** Format: date-time */
            expires_at: string;
            finalize_url: string;
            /** Format: uuid */
            id: string;
            kind: components["schemas"]["VisitPhotoKindEnum"];
            max_bytes: number;
            /** Format: uuid */
            visit_id: string;
        };
        VisitReceivable: {
            amount_minor: number;
            /** Format: date-time */
            created_at: string;
            /** Format: uuid */
            id: string;
            status: components["schemas"]["ReceivableStatusEnum"];
        };
        VisitRecommendation: {
            author_id: number;
            author_name: string;
            /** Format: date-time */
            created_at: string;
            /** Format: uuid */
            id: string;
            text: string;
            /** Format: date-time */
            updated_at: string;
            version: number;
        };
        VisitRecommendationCreateRequest: {
            text: string;
        };
        VisitResponse: {
            appointment: components["schemas"]["VisitAppointment"];
            complaints: string;
            /** Format: date-time */
            completed_at: string | null;
            detected_conditions: components["schemas"]["DetectedConditionEnum"][];
            editable: boolean;
            has_no_complaints: boolean;
            /** Format: uuid */
            id: string;
            material_lines: components["schemas"]["VisitMaterialLine"][];
            objective_examination: string;
            patient: components["schemas"]["VisitPatient"];
            payment_handoff_requested: boolean;
            photos: components["schemas"]["VisitPhoto"][];
            podologist_notes: string;
            public_number: string;
            recommendations: components["schemas"]["VisitRecommendation"][];
            service_lines: components["schemas"]["VisitServiceLine"][];
            services_total_minor: number;
            specialist: components["schemas"]["VisitSpecialist"];
            /** Format: date-time */
            started_at: string;
            status: components["schemas"]["VisitStatusEnum"];
            total_minor: number | null;
            /** Format: date-time */
            updated_at: string;
            version: number;
        };
        VisitServiceLine: {
            duration_minutes: number;
            /** Format: uuid */
            id: string;
            is_primary: boolean;
            line_total_minor: number;
            price_minor: number;
            quantity: number;
            service_code: string;
            /** Format: uuid */
            service_id: string;
            service_name: string;
        };
        VisitServiceLineInputRequest: {
            quantity: number;
            /** Format: uuid */
            service_id: string;
        };
        VisitSpecialist: {
            display_name: string;
            id: number;
        };
        /**
         * @description * `DRAFT` - Чернетка
         *     * `COMPLETED` - Завершено
         * @enum {string}
         */
        VisitStatusEnum: "DRAFT" | "COMPLETED";
        WorkItem: {
            readonly assignee: components["schemas"]["WorkItemAssignee"];
            comment?: string;
            /** Format: date-time */
            completed_at?: string | null;
            readonly completed_by: components["schemas"]["WorkItemAssignee"] | null;
            /** Format: date-time */
            readonly created_at: string;
            readonly created_by: components["schemas"]["WorkItemAssignee"];
            /** Format: date-time */
            due_at: string;
            /** Format: uuid */
            readonly id: string;
            is_completed?: boolean;
            is_important?: boolean;
            readonly is_overdue: boolean;
            kind: components["schemas"]["WorkItemKindEnum"];
            readonly kind_label: string;
            readonly patient: components["schemas"]["WorkItemPatient"] | null;
            title: string;
            /** Format: date-time */
            readonly updated_at: string;
            version?: number;
        };
        WorkItemAssignee: {
            readonly display_name: string;
            readonly id: number;
            role: components["schemas"]["RoleEnum"];
        };
        WorkItemCreateRequest: {
            assignee_id: number;
            comment?: string;
            /** Format: date-time */
            due_at: string;
            /** @default false */
            is_important: boolean;
            kind: components["schemas"]["WorkItemKindEnum"];
            /** Format: uuid */
            patient_id?: string | null;
            title: string;
        };
        /**
         * @description * `callback` - Перетелефонувати
         *     * `confirm_appointment` - Підтвердити запис
         *     * `manual_message` - Написати пацієнту вручну
         *     * `other` - Інша внутрішня справа
         * @enum {string}
         */
        WorkItemKindEnum: "callback" | "confirm_appointment" | "manual_message" | "other";
        WorkItemListResponse: {
            assignees: components["schemas"]["WorkItemAssignee"][];
            effective_scope: components["schemas"]["EffectiveScopeEnum"];
            summary: components["schemas"]["WorkItemSummary"];
            work_items: components["schemas"]["WorkItem"][];
        };
        WorkItemPatient: {
            readonly display_name: string;
            /** Format: uuid */
            readonly id: string;
            phone: string;
            readonly public_number: string;
        };
        WorkItemSummary: {
            completed: number;
            important: number;
            open: number;
            overdue: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    analytics_retrieve: {
        parameters: {
            query: {
                from: string;
                service_id?: string;
                specialist_id?: number;
                to: string;
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
                    "application/json": components["schemas"]["AnalyticsResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    analytics_export: {
        parameters: {
            query: {
                format?: "csv" | "json";
                from: string;
                service_id?: string;
                specialist_id?: number;
                to: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description UTF-8 BOM CSV with an aggregate summary and at most 5000 trend/outcome/specialist/service rows. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": string;
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    appointment_status_config_list: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["AppointmentStatusConfigList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    appointment_status_config_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                code: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedAppointmentStatusConfigUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedAppointmentStatusConfigUpdateRequest"];
                "multipart/form-data": components["schemas"]["PatchedAppointmentStatusConfigUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AppointmentStatusConfig"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    appointment_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AppointmentCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["AppointmentCreateRequest"];
                "multipart/form-data": components["schemas"]["AppointmentCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AppointmentResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    appointment_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                appointment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AppointmentDetailResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    appointment_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                appointment_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": {
                    comment?: string;
                    complaints?: string;
                    has_no_complaints?: boolean;
                    /** Format: uuid */
                    room_id?: string;
                    /** Format: uuid */
                    service_id?: string;
                    specialist_id?: number;
                    /** Format: date-time */
                    starts_at?: string;
                    version: number;
                };
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AppointmentDetailResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    appointment_cancel: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                appointment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AppointmentCancelRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["AppointmentCancelRequest"];
                "multipart/form-data": components["schemas"]["AppointmentCancelRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AppointmentDetailResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    visit_start: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                appointment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StartVisitRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["StartVisitRequest"];
                "multipart/form-data": components["schemas"]["StartVisitRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitResponse"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    appointment_status_transition: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                appointment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AppointmentStatusTransitionRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["AppointmentStatusTransitionRequest"];
                "multipart/form-data": components["schemas"]["AppointmentStatusTransitionRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AppointmentDetailResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    appointment_availability_retrieve: {
        parameters: {
            query: {
                date: string;
                room_id?: string;
                service_id: string;
                specialist_id: number;
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
                    "application/json": components["schemas"]["AvailabilityResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    audit_event_list: {
        parameters: {
            query?: {
                actor_id?: number;
                cursor?: string;
                date_from?: string;
                date_to?: string;
                search?: string;
                /**
                 * @description * `accounts` - accounts
                 *     * `team` - team
                 *     * `settings` - settings
                 *     * `patients` - patients
                 *     * `work_items` - work_items
                 *     * `booking_requests` - booking_requests
                 *     * `scheduling` - scheduling
                 *     * `medical` - medical
                 *     * `visits` - visits
                 *     * `billing` - billing
                 *     * `cash` - cash
                 *     * `inventory` - inventory
                 */
                section?: "accounts" | "team" | "settings" | "patients" | "work_items" | "booking_requests" | "scheduling" | "medical" | "visits" | "billing" | "cash" | "inventory";
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
                    "application/json": components["schemas"]["AuditEventListResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    audit_event_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                event_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditEventDetail"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    audit_event_export: {
        parameters: {
            query?: {
                actor_id?: number;
                date_from?: string;
                date_to?: string;
                format?: "csv" | "json";
                search?: string;
                /**
                 * @description * `accounts` - accounts
                 *     * `team` - team
                 *     * `settings` - settings
                 *     * `patients` - patients
                 *     * `work_items` - work_items
                 *     * `booking_requests` - booking_requests
                 *     * `scheduling` - scheduling
                 *     * `medical` - medical
                 *     * `visits` - visits
                 *     * `billing` - billing
                 *     * `cash` - cash
                 *     * `inventory` - inventory
                 */
                section?: "accounts" | "team" | "settings" | "patients" | "work_items" | "booking_requests" | "scheduling" | "medical" | "visits" | "billing" | "cash" | "inventory";
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description UTF-8 BOM CSV with one report summary and at most 5000 minimal audit-event rows. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": string;
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    auth_change_password: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChangePasswordRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ChangePasswordRequestRequest"];
                "multipart/form-data": components["schemas"]["ChangePasswordRequestRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    auth_first_login_password: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordPairRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PasswordPairRequest"];
                "multipart/form-data": components["schemas"]["PasswordPairRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    auth_login: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["LoginRequestRequest"];
                "multipart/form-data": components["schemas"]["LoginRequestRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    auth_logout: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    booking_request_integration_retrieve: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["BookingRequestApiCredential"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    booking_request_integration_token_rotate: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BookingRequestApiCredentialRotateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["BookingRequestApiCredentialRotateRequest"];
                "multipart/form-data": components["schemas"]["BookingRequestApiCredentialRotateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BookingRequestApiCredentialRotated"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    booking_request_list: {
        parameters: {
            query?: {
                cursor?: string;
                search?: string;
                /**
                 * @description * `ALL` - ALL
                 *     * `INSTAGRAM` - INSTAGRAM
                 *     * `FACEBOOK` - FACEBOOK
                 *     * `WEBSITE` - WEBSITE
                 */
                source?: "ALL" | "INSTAGRAM" | "FACEBOOK" | "WEBSITE";
                /**
                 * @description * `ALL` - ALL
                 *     * `NEW` - NEW
                 *     * `PROCESSED` - PROCESSED
                 */
                status?: "ALL" | "NEW" | "PROCESSED";
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
                    "application/json": components["schemas"]["BookingRequestListResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    booking_request_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                booking_request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BookingRequest"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    booking_request_process: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                booking_request_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BookingRequestProcessRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["BookingRequestProcessRequest"];
                "multipart/form-data": components["schemas"]["BookingRequestProcessRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BookingRequest"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    calendar_retrieve: {
        parameters: {
            query: {
                from: string;
                specialist_id?: number;
                to: string;
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
                    "application/json": components["schemas"]["CalendarResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    cash_movement_create: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable per-submit key. The same normalized payload replays its result. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CashMovementCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["CashMovementCreateRequest"];
                "multipart/form-data": components["schemas"]["CashMovementCreateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CashMovementCreateResponse"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CashMovementCreateResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    cash_shift_list: {
        parameters: {
            query?: {
                cursor?: string;
                date_from?: string;
                date_to?: string;
                employee_id?: number;
                search?: string;
                /**
                 * @description * `OPEN` - Відкрита
                 *     * `CLOSED` - Закрита
                 */
                status?: "OPEN" | "CLOSED";
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
                    "application/json": components["schemas"]["CashShiftListResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    cash_shift_open: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CashShiftProjection"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    cash_shift_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                shift_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CashShiftProjection"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    cash_shift_close: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable per-submit key. The same normalized payload replays its result. */
                "Idempotency-Key": string;
            };
            path: {
                shift_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CashShiftCloseRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["CashShiftCloseRequest"];
                "multipart/form-data": components["schemas"]["CashShiftCloseRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CashShiftCloseResponse"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CashShiftCloseResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    cash_shift_close_preview: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                shift_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CashShiftClosePreviewResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    cash_shift_export: {
        parameters: {
            query?: {
                format?: "csv" | "json";
            };
            header?: never;
            path: {
                shift_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description UTF-8 BOM CSV with one summary row and at most 5000 ledger rows. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": string;
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    cash_shift_current: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["CashShiftCurrentResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    cash_shift_history_export: {
        parameters: {
            query?: {
                date_from?: string;
                date_to?: string;
                employee_id?: number;
                format?: "csv" | "json";
                search?: string;
                /**
                 * @description * `OPEN` - Відкрита
                 *     * `CLOSED` - Закрита
                 */
                status?: "OPEN" | "CLOSED";
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description UTF-8 BOM CSV with one report summary and at most 5000 cash-shift rows. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": string;
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    clinic_profile_retrieve: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["ClinicProfile"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    clinic_profile_update: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedClinicProfileUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedClinicProfileUpdateRequest"];
                "multipart/form-data": components["schemas"]["PatchedClinicProfileUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClinicProfile"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    clinic_logo_retrieve: {
        parameters: {
            query?: never;
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
                    "image/png": string;
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    clinic_logo_update: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["ClinicLogoUploadRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClinicProfile"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    clinic_workday_list: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["ClinicWorkdayList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    clinic_workday_update: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClinicScheduleUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ClinicScheduleUpdateRequest"];
                "multipart/form-data": components["schemas"]["ClinicScheduleUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClinicWorkdayList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    finance_operation_list: {
        parameters: {
            query?: {
                amount_minor?: number;
                cursor?: string;
                date_from?: string;
                date_to?: string;
                patient_id?: string;
                /**
                 * @description * `CASH` - CASH
                 *     * `CARD` - CARD
                 *     * `TRANSFER` - TRANSFER
                 */
                payment_method?: "CASH" | "CARD" | "TRANSFER";
                refundable_only?: boolean;
                search?: string;
                /**
                 * @description * `OPEN` - OPEN
                 *     * `PAID` - PAID
                 *     * `REFUNDED` - REFUNDED
                 *     * `POSTED` - POSTED
                 */
                status?: "OPEN" | "PAID" | "REFUNDED" | "POSTED";
                /**
                 * @description * `PAYMENT` - PAYMENT
                 *     * `REFUND` - REFUND
                 *     * `DEPOSIT` - DEPOSIT
                 *     * `WITHDRAWAL` - WITHDRAWAL
                 */
                type?: "PAYMENT" | "REFUND" | "DEPOSIT" | "WITHDRAWAL";
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
                    "application/json": components["schemas"]["FinanceOperationListResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    finance_operation_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
                operation_type: "PAYMENT";
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FinancePaymentOperation"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    finance_operation_export: {
        parameters: {
            query?: {
                date_from?: string;
                date_to?: string;
                format?: "csv" | "json";
                /**
                 * @description * `CASH` - CASH
                 *     * `CARD` - CARD
                 *     * `TRANSFER` - TRANSFER
                 */
                payment_method?: "CASH" | "CARD" | "TRANSFER";
                search?: string;
                /**
                 * @description * `OPEN` - OPEN
                 *     * `PAID` - PAID
                 *     * `REFUNDED` - REFUNDED
                 *     * `POSTED` - POSTED
                 */
                status?: "OPEN" | "PAID" | "REFUNDED" | "POSTED";
                /**
                 * @description * `PAYMENT` - PAYMENT
                 *     * `REFUND` - REFUND
                 *     * `DEPOSIT` - DEPOSIT
                 *     * `WITHDRAWAL` - WITHDRAWAL
                 */
                type?: "PAYMENT" | "REFUND" | "DEPOSIT" | "WITHDRAWAL";
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description UTF-8 BOM CSV with one report summary and at most 5000 finance-operation rows. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": string;
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    external_booking_request_create: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable unique value for one logical form submission. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExternalBookingRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ExternalBookingRequestRequest"];
                "multipart/form-data": components["schemas"]["ExternalBookingRequestRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExternalBookingRequestResponse"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExternalBookingRequestResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
            /** @description Rate limit exceeded; Retry-After is included. */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    telegram_webhook_receive: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
                "application/x-www-form-urlencoded": {
                    [key: string]: unknown;
                };
                "multipart/form-data": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    inventory_material_list: {
        parameters: {
            query?: {
                category?: string;
                search?: string;
                /**
                 * @description * `all` - all
                 *     * `active` - active
                 *     * `inactive` - inactive
                 */
                status?: "all" | "active" | "inactive";
                /**
                 * @description * `all` - all
                 *     * `out_of_stock` - out_of_stock
                 *     * `low` - low
                 *     * `expired` - expired
                 *     * `expiring` - expiring
                 *     * `healthy` - healthy
                 */
                stock_status?: "all" | "out_of_stock" | "low" | "expired" | "expiring" | "healthy";
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
                    "application/json": components["schemas"]["MaterialList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_material_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaterialCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["MaterialCreateRequest"];
                "multipart/form-data": components["schemas"]["MaterialCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Material"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_material_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                material_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Material"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    inventory_material_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                material_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedMaterialUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedMaterialUpdateRequest"];
                "multipart/form-data": components["schemas"]["PatchedMaterialUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Material"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_material_lot_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                material_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MaterialLotList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    inventory_movement_list: {
        parameters: {
            query?: {
                actor?: string;
                cursor?: string;
                date_from?: string;
                date_to?: string;
                /**
                 * @description * `all` - all
                 *     * `RECEIPT` - RECEIPT
                 *     * `VISIT_USAGE` - VISIT_USAGE
                 *     * `MANUAL_WRITEOFF` - MANUAL_WRITEOFF
                 *     * `STOCKTAKE_ADJUSTMENT` - STOCKTAKE_ADJUSTMENT
                 */
                kind?: "all" | "RECEIPT" | "VISIT_USAGE" | "MANUAL_WRITEOFF" | "STOCKTAKE_ADJUSTMENT";
                material_id?: string;
                search?: string;
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
                    "application/json": components["schemas"]["MovementJournalResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_movement_export: {
        parameters: {
            query?: {
                actor?: string;
                date_from?: string;
                date_to?: string;
                format?: "csv" | "json";
                /**
                 * @description * `all` - all
                 *     * `RECEIPT` - RECEIPT
                 *     * `VISIT_USAGE` - VISIT_USAGE
                 *     * `MANUAL_WRITEOFF` - MANUAL_WRITEOFF
                 *     * `STOCKTAKE_ADJUSTMENT` - STOCKTAKE_ADJUSTMENT
                 */
                kind?: "all" | "RECEIPT" | "VISIT_USAGE" | "MANUAL_WRITEOFF" | "STOCKTAKE_ADJUSTMENT";
                material_id?: string;
                search?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description UTF-8 BOM CSV attachment with at most 5000 movement rows. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": string;
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                    "text/csv": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    inventory_operation_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InventoryOperation"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    inventory_receipt_create: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable per-submit key. A retry with the same payload returns the original operation. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReceiptCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ReceiptCreateRequest"];
                "multipart/form-data": components["schemas"]["ReceiptCreateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InventoryOperation"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InventoryOperation"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_stocktake_create: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable per-submit key. A retry with the same payload returns the original operation. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StocktakeCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["StocktakeCreateRequest"];
                "multipart/form-data": components["schemas"]["StocktakeCreateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Stocktake"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Stocktake"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_stocktake_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                stocktake_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Stocktake"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    inventory_stocktake_post: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable per-submit key. A retry with the same payload returns the original operation. */
                "Idempotency-Key": string;
            };
            path: {
                stocktake_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Stocktake"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_stocktake_preview: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["StocktakePreview"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    inventory_supplier_list: {
        parameters: {
            query?: {
                search?: string;
                /**
                 * @description * `all` - all
                 *     * `active` - active
                 *     * `inactive` - inactive
                 */
                status?: "all" | "active" | "inactive";
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
                    "application/json": components["schemas"]["SupplierList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_supplier_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SupplierCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["SupplierCreateRequest"];
                "multipart/form-data": components["schemas"]["SupplierCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Supplier"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_supplier_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                supplier_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Supplier"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    inventory_supplier_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                supplier_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedSupplierUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedSupplierUpdateRequest"];
                "multipart/form-data": components["schemas"]["PatchedSupplierUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Supplier"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    inventory_manual_writeoff_create: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable per-submit key. A retry with the same payload returns the original operation. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ManualWriteoffCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ManualWriteoffCreateRequest"];
                "multipart/form-data": components["schemas"]["ManualWriteoffCreateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InventoryOperation"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InventoryOperation"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    notification_list: {
        parameters: {
            query?: {
                cursor?: string;
                /**
                 * @description * `all` - all
                 *     * `unread` - unread
                 */
                status?: "all" | "unread";
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
                    "application/json": components["schemas"]["NotificationListResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    notification_read: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                notification_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Notification"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    notification_read_all: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["NotificationMarkAllResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    overview_retrieve: {
        parameters: {
            query?: {
                date?: string;
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
                    "application/json": components["schemas"]["OverviewResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    password_reset_request_list: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["PasswordResetRequestList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    password_reset_request_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordResetRequestCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PasswordResetRequestCreateRequest"];
                "multipart/form-data": components["schemas"]["PasswordResetRequestCreateRequest"];
            };
        };
        responses: {
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PasswordResetRequestAccepted"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    patient_list: {
        parameters: {
            query?: {
                cursor?: string;
                search?: string;
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
                    "application/json": components["schemas"]["PatientListResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    patient_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PatientCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatientCreateRequest"];
                "multipart/form-data": components["schemas"]["PatientCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PatientCreateResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    patient_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PatientDetailResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    patient_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedPatientUpdateRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedPatientUpdateRequestRequest"];
                "multipart/form-data": components["schemas"]["PatchedPatientUpdateRequestRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PatientDetailResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    patient_photo_archive: {
        parameters: {
            query?: {
                cursor?: string;
            };
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PatientPhotoArchiveResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    patient_recommendation_list: {
        parameters: {
            query?: {
                cursor?: string;
            };
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PatientRecommendationResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    patient_visit_history: {
        parameters: {
            query?: {
                cursor?: string;
            };
            header?: never;
            path: {
                patient_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PatientHistoryResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    payment_create: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable per-submit key. The same normalized payload replays its result. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PaymentCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PaymentCreateRequest"];
                "multipart/form-data": components["schemas"]["PaymentCreateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaymentCreateResponse"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaymentCreateResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    refund_create: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable per-submit key. The same normalized payload replays its result. */
                "Idempotency-Key": string;
            };
            path: {
                payment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RefundCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["RefundCreateRequest"];
                "multipart/form-data": components["schemas"]["RefundCreateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RefundCreateResponse"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RefundCreateResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    room_list: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["RoomList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    room_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RoomCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["RoomCreateRequest"];
                "multipart/form-data": components["schemas"]["RoomCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Room"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    room_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                room_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedRoomUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedRoomUpdateRequest"];
                "multipart/form-data": components["schemas"]["PatchedRoomUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Room"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    global_search_list: {
        parameters: {
            query: {
                q: string;
                types?: string;
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
                    "application/json": components["schemas"]["GlobalSearchResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    service_list: {
        parameters: {
            query?: {
                search?: string;
                /**
                 * @description * `all` - all
                 *     * `active` - active
                 *     * `inactive` - inactive
                 */
                status?: "all" | "active" | "inactive";
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
                    "application/json": components["schemas"]["ServiceList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    service_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ServiceCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ServiceCreateRequest"];
                "multipart/form-data": components["schemas"]["ServiceCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Service"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    service_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                service_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Service"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    service_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                service_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedServiceUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedServiceUpdateRequest"];
                "multipart/form-data": components["schemas"]["PatchedServiceUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Service"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    session_retrieve: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["Session"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    telegram_link_intent_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TelegramLinkIntent"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    telegram_subscription_retrieve: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["TelegramSubscription"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    telegram_subscription_disconnect: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    team_user_list: {
        parameters: {
            query?: {
                /**
                 * @description * `podologist` - Подолог
                 *     * `reception` - Рецепція
                 *     * `admin` - Адміністратор
                 */
                role?: "podologist" | "reception" | "admin";
                search?: string;
                /**
                 * @description * `all` - all
                 *     * `active` - active
                 *     * `inactive` - inactive
                 */
                status?: "all" | "active" | "inactive";
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
                    "application/json": components["schemas"]["TeamUserList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    team_user_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TeamUserCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["TeamUserCreateRequest"];
                "multipart/form-data": components["schemas"]["TeamUserCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeamUser"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    team_user_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeamUser"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    team_user_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedTeamUserUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedTeamUserUpdateRequest"];
                "multipart/form-data": components["schemas"]["PatchedTeamUserUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeamUser"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    team_user_deactivate: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeamUser"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    user_temporary_password_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemporaryPasswordRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["TemporaryPasswordRequestRequest"];
                "multipart/form-data": components["schemas"]["TemporaryPasswordRequestRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemporaryPasswordResult"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    visit_photo_content_retrieve: {
        parameters: {
            query: {
                token: string;
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
                    "image/jpeg": string;
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    visit_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    visit_draft_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VisitDraftUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["VisitDraftUpdateRequest"];
                "multipart/form-data": components["schemas"]["VisitDraftUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    visit_finish: {
        parameters: {
            query?: never;
            header: {
                /** @description Stable per-submit key. Same payload replays the original completion result. */
                "Idempotency-Key": string;
            };
            path: {
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VisitFinishRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["VisitFinishRequest"];
                "multipart/form-data": components["schemas"]["VisitFinishRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitFinishResponse"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitFinishResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    visit_material_option_list: {
        parameters: {
            query?: {
                search?: string;
            };
            header?: never;
            path: {
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitMaterialOptionList"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    visit_photo_finalize: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["VisitPhotoFinalizeRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitPhoto"];
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitPhoto"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    visit_photo_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitPhoto"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    visit_photo_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    visit_photo_upload_intent_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VisitPhotoIntentCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["VisitPhotoIntentCreateRequest"];
                "multipart/form-data": components["schemas"]["VisitPhotoIntentCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitPhotoUploadIntent"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    visit_recommendation_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VisitRecommendationCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["VisitRecommendationCreateRequest"];
                "multipart/form-data": components["schemas"]["VisitRecommendationCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitRecommendation"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    visit_recommendation_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                recommendation_id: string;
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitRecommendation"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    visit_recommendation_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                recommendation_id: string;
                visit_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedVisitRecommendationUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedVisitRecommendationUpdateRequest"];
                "multipart/form-data": components["schemas"]["PatchedVisitRecommendationUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisitRecommendation"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    work_item_list: {
        parameters: {
            query?: {
                /**
                 * @description * `own` - own
                 *     * `all` - all
                 */
                scope?: "own" | "all";
                search?: string;
                /**
                 * @description * `open` - open
                 *     * `completed` - completed
                 *     * `all` - all
                 */
                status?: "open" | "completed" | "all";
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
                    "application/json": components["schemas"]["WorkItemListResponse"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    work_item_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkItemCreateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["WorkItemCreateRequest"];
                "multipart/form-data": components["schemas"]["WorkItemCreateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
    work_item_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                work_item_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PatchedWorkItemUpdateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedWorkItemUpdateRequest"];
                "multipart/form-data": components["schemas"]["PatchedWorkItemUpdateRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkItem"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
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
