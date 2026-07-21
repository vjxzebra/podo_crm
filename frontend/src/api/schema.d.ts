// Generated from backend/openapi/schema.json. Do not edit by hand.
export interface paths {
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
            status: components["schemas"]["StatusEnum"];
        };
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
        /**
         * @description * `callback` - Перетелефонувати
         *     * `confirm_appointment` - Підтвердити запис
         *     * `manual_message` - Написати пацієнту вручну
         *     * `other` - Інша внутрішня справа
         * @enum {string}
         */
        KindEnum: "callback" | "confirm_appointment" | "manual_message" | "other";
        LoginRequestRequest: {
            email: string;
            password: string;
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
            readonly visit_history: components["schemas"]["PatientVisitHistoryItem"][];
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
        PatchedTeamUserUpdateRequest: {
            /** Format: email */
            email?: string;
            first_name?: string;
            is_active?: boolean;
            last_name?: string;
            phone?: string;
            role?: components["schemas"]["RoleEnum"];
        };
        PatchedWorkItemUpdateRequest: {
            assignee_id?: number;
            comment?: string;
            /** Format: date-time */
            due_at?: string;
            is_completed?: boolean;
            is_important?: boolean;
            kind?: components["schemas"]["KindEnum"];
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
        PatientPhotoVisitMetadata: {
            after_count: number;
            before_count: number;
            caption: string;
            /** Format: date-time */
            occurred_at: string;
            /** Format: uuid */
            visit_id: string;
        };
        PatientVisitHistoryItem: {
            cost_minor: number;
            has_photos: boolean;
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            occurred_at: string;
            services: string[];
            specialist: string;
            status: string;
            summary: string;
        };
        PodologistSummary: {
            readonly display_name: string;
            readonly id: number;
        };
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
            readonly visit_history: components["schemas"]["PatientVisitHistoryItem"][];
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
         * @description * `ok` - ok
         * @enum {string}
         */
        StatusEnum: "ok";
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
            kind: components["schemas"]["KindEnum"];
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
            kind: components["schemas"]["KindEnum"];
            /** Format: uuid */
            patient_id?: string | null;
            title: string;
        };
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
                 *     * `scheduling` - scheduling
                 *     * `medical` - medical
                 *     * `visits` - visits
                 *     * `billing` - billing
                 *     * `cash` - cash
                 *     * `inventory` - inventory
                 */
                section?: "accounts" | "team" | "settings" | "patients" | "work_items" | "scheduling" | "medical" | "visits" | "billing" | "cash" | "inventory";
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
