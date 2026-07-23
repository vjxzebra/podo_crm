import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

export const adminSession = {
  user: {
    id: 1,
    email: "admin@example.test",
    display_name: "Тест Адміністратор",
    role: "admin",
  },
  route_ids: [
    "overview",
    "calendar",
    "patients",
    "work-items",
    "finance",
    "inventory",
    "analytics",
    "notifications",
    "audit",
    "team",
    "settings",
    "password-resets",
    "contracts",
  ],
  notification_unread_count: 0,
  must_change_password: false,
  temporary_password_expires_at: null,
  temporary_password_expired: false,
} as const;

export const receptionSession = {
  user: {
    id: 2,
    email: "reception@example.test",
    display_name: "Тест Рецепція",
    role: "reception",
  },
  route_ids: ["overview", "calendar", "patients", "work-items", "finance", "notifications"],
  notification_unread_count: 0,
  must_change_password: false,
  temporary_password_expires_at: null,
  temporary_password_expired: false,
} as const;

export const podologistSession = {
  user: {
    id: 4,
    email: "podologist@example.test",
    display_name: "Олена Подолог",
    role: "podologist",
  },
  route_ids: ["overview", "calendar", "patients", "work-items", "notifications"],
  notification_unread_count: 0,
  must_change_password: false,
  temporary_password_expires_at: null,
  temporary_password_expired: false,
} as const;

export const forcedPasswordSession = {
  user: {
    id: 3,
    email: "olena@example.test",
    display_name: "Олена Мельник",
    role: "podologist",
  },
  route_ids: [],
  notification_unread_count: 0,
  must_change_password: true,
  temporary_password_expires_at: "2026-07-21T12:00:00+03:00",
  temporary_password_expired: false,
} as const;

export const anonymousProblem = {
  code: "authentication_required",
  message: "Потрібна автентифікація.",
  fields: {},
  correlation_id: "test-request",
};

export const clinicProfile = {
  name: "Podoria Clinic",
  phone: "+380 67 111 22 33",
  email: "clinic@podoria.test",
  address: "Київ, вул. Прикладна, 10",
  description: "Професійний догляд за стопами та нігтями.",
  has_logo: false,
  logo_url: null,
  logo_content_type: "",
  logo_size: null,
  version: 1,
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

export const clinicRoom = {
  id: "8b169a0d-ff81-45b7-ab3f-ed91031d3b5e",
  name: "Кабінет 1",
  is_active: true,
  version: 1,
  created_at: "2026-07-21T12:00:00+03:00",
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

export const clinicService = {
  id: "2f811768-f227-4b3b-896b-31b0960b8a20",
  code: "CONSULT",
  name: "Первинна консультація",
  duration_minutes: 45,
  price_minor: 120000,
  color: "#0F766E",
  is_active: true,
  version: 1,
  created_at: "2026-07-21T12:00:00+03:00",
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

export const inventoryMaterial = {
  id: "d8be8f1a-4487-43d5-9232-32891566f41a",
  sku: "KAP-001",
  name: "Каполін, 1 см",
  category: "Перев’язувальні",
  unit: "шт.",
  minimum_quantity: "20.000",
  is_active: true,
  total_quantity: "12.000",
  available_quantity: "12.000",
  nearest_expiry: "2027-08-31",
  stock_status: "low",
  lots_count: 2,
  version: 1,
  created_at: "2026-07-21T12:00:00+03:00",
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

export const healthyInventoryMaterial = {
  ...inventoryMaterial,
  id: "4d8a1f8f-5cab-4c7d-b2d4-a2c5ffb3ec01",
  sku: "GLO-006",
  name: "Рукавички нітрилові M",
  category: "Захист",
  unit: "пар",
  minimum_quantity: "100.000",
  total_quantity: "240.000",
  available_quantity: "240.000",
  nearest_expiry: "2028-04-30",
  stock_status: "healthy",
  lots_count: 1,
} as const;

export const inventorySupplier = {
  id: "a4f59f8a-5c2f-41c0-8f10-9b85e9b952ad",
  name: "Podology Market",
  contact_name: "Олена Коваль",
  phone: "+380 67 123 45 67",
  email: "sales@podology-market.test",
  address: "Київ, вул. Тестова, 1",
  note: "Доставка щовівторка",
  is_active: true,
  lots_count: 1,
  version: 1,
  created_at: "2026-07-21T12:00:00+03:00",
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

export const inactiveInventorySupplier = {
  ...inventorySupplier,
  id: "51636d4a-4962-4a3d-9472-96c7ff3ac624",
  name: "ТОВ Медтехніка",
  contact_name: "",
  phone: "",
  email: "",
  address: "",
  note: "",
  is_active: false,
  lots_count: 1,
} as const;

export const inventoryLots = [
  {
    id: "8cc5bb98-4bd6-4ea6-b167-dd7c3fe1b11d",
    lot_number: "N-038 / 03",
    received_on: "2026-06-28",
    expires_on: "2027-08-31",
    initial_quantity: "10.000",
    current_quantity: "4.000",
    purchase_price_minor: 320,
    supplier_id: inventorySupplier.id,
    supplier_name: "Podology Market",
    is_expired: false,
    is_usable: true,
    status: "usable",
    fefo_rank: 1,
    created_at: "2026-06-28T12:00:00+03:00",
  },
  {
    id: "395230bb-7ad7-46db-b4de-d6b76a2677fd",
    lot_number: "N-042 / 01",
    received_on: "2026-07-14",
    expires_on: "2027-11-30",
    initial_quantity: "20.000",
    current_quantity: "8.000",
    purchase_price_minor: 320,
    supplier_id: inactiveInventorySupplier.id,
    supplier_name: "ТОВ Медтехніка",
    is_expired: false,
    is_usable: true,
    status: "usable",
    fefo_rank: 2,
    created_at: "2026-07-14T12:00:00+03:00",
  },
] as const;

export const inventoryReceiptOperation = {
  id: "f87830c1-53ad-4752-b2f9-23042337fdc0",
  public_number: "INV-F87830C153AD",
  kind: "RECEIPT",
  status: "POSTED",
  created_by_id: 1,
  created_by_name: "Олена Коваль",
  created_by_email: "admin@podoria.local",
  reason: "",
  comment: "Планове поповнення",
  posted_at: "2026-07-21T18:30:00Z",
  replayed: false,
  movement_count: 1,
  movements: [{
    id: "d408a7bc-9cd5-4225-a85d-530dccf77f38",
    material_id: inventoryMaterial.id,
    material_name: inventoryMaterial.name,
    material_unit: inventoryMaterial.unit,
    lot_id: "8a1601a2-6ac3-40a7-9fa8-218026be904f",
    lot_number: "N-050",
    supplier_id: inventorySupplier.id,
    supplier_name: inventorySupplier.name,
    quantity_delta: "15.000",
    balance_after: "15.000",
    created_at: "2026-07-21T18:30:00Z",
  }],
} as const;

export const inventoryWriteoffOperation = {
  ...inventoryReceiptOperation,
  id: "7b99a2d9-28ad-46f0-848c-d32ddd64e12a",
  public_number: "INV-7B99A2D928AD",
  kind: "MANUAL_WRITEOFF",
  reason: "Пошкодження",
  comment: "Пошкоджене пакування",
  movements: [{
    ...inventoryReceiptOperation.movements[0],
    id: "36a6b36b-2f16-4692-828a-2b60d211214e",
    lot_id: inventoryLots[0].id,
    lot_number: inventoryLots[0].lot_number,
    quantity_delta: "-2.000",
    balance_after: "2.000",
  }],
} as const;

export const stocktakePreview = {
  lots: inventoryLots.map((lot) => ({
    id: lot.id,
    material_id: inventoryMaterial.id,
    material_sku: inventoryMaterial.sku,
    material_name: inventoryMaterial.name,
    material_unit: inventoryMaterial.unit,
    lot_number: lot.lot_number,
    system_quantity: lot.current_quantity,
    purchase_price_minor: lot.purchase_price_minor,
    expires_on: lot.expires_on,
    is_expired: lot.is_expired,
  })),
} as const;

export const stocktakeDraft = {
  id: "7b6ea87c-9f1d-48e6-a664-9e55534aa85b",
  public_number: "STK-7B6EA87C9F1D",
  status: "DRAFT",
  created_by_id: 1,
  created_by_name: "Олена Коваль",
  posted_by_id: null,
  posted_by_name: null,
  comment: "Щомісячний контроль",
  operation_id: null,
  created_at: "2026-07-21T18:45:00Z",
  posted_at: null,
  line_count: 2,
  adjusted_line_count: 1,
  surplus_line_count: 1,
  shortage_line_count: 0,
  adjustment_value_minor: 640,
  unpriced_adjustment_count: 0,
  replayed: false,
  lines: stocktakePreview.lots.map((lot, index) => ({
    id: index === 0
      ? "21218194-9ad8-49c8-a51b-dd01f8cfba64"
      : "8a4df5b9-4a2d-4521-b2d3-37fbc616f26d",
    lot_id: lot.id,
    material_sku: lot.material_sku,
    material_name: lot.material_name,
    material_unit: lot.material_unit,
    lot_number: lot.lot_number,
    system_quantity: lot.system_quantity,
    actual_quantity: index === 0 ? "6.000" : lot.system_quantity,
    difference: index === 0 ? "2.000" : "0.000",
    difference_kind: index === 0 ? "SURPLUS" : "MATCH",
    purchase_price_minor: lot.purchase_price_minor,
    adjustment_value_minor: index === 0 ? 640 : 0,
  })),
} as const;

export const stocktakePosted = {
  ...stocktakeDraft,
  status: "POSTED",
  posted_by_id: 1,
  posted_by_name: "Олена Коваль",
  operation_id: "8df44a88-846f-4adf-a1bd-a6f97189ae11",
  posted_at: "2026-07-21T18:46:00Z",
} as const;

export const inventoryMovementJournal = {
  movements: [
    {
      id: "a8a9429b-2982-4a79-b3e7-055353848170",
      operation_id: stocktakePosted.operation_id,
      operation_public_number: "INV-8DF44A88846F",
      operation_kind: "STOCKTAKE_ADJUSTMENT",
      operation_reason: `Інвентаризація ${stocktakePosted.public_number}`,
      operation_comment: stocktakePosted.comment,
      posted_at: stocktakePosted.posted_at,
      actor_id: 1,
      actor_name: "Олена Коваль",
      actor_email: "admin@podoria.local",
      material_id: inventoryMaterial.id,
      material_sku: inventoryMaterial.sku,
      material_name: inventoryMaterial.name,
      material_unit: inventoryMaterial.unit,
      lot_id: inventoryLots[0].id,
      lot_number: inventoryLots[0].lot_number,
      quantity_delta: "2.000",
      balance_after: "6.000",
      created_at: stocktakePosted.posted_at,
    },
  ],
  next_cursor: null,
} as const;

export const stocktakeOperationDetail = {
  ...inventoryReceiptOperation,
  id: stocktakePosted.operation_id,
  public_number: inventoryMovementJournal.movements[0].operation_public_number,
  kind: "STOCKTAKE_ADJUSTMENT",
  reason: inventoryMovementJournal.movements[0].operation_reason,
  comment: stocktakePosted.comment,
  posted_at: stocktakePosted.posted_at,
  movements: [{
    id: inventoryMovementJournal.movements[0].id,
    material_id: inventoryMaterial.id,
    material_name: inventoryMaterial.name,
    material_unit: inventoryMaterial.unit,
    lot_id: inventoryLots[0].id,
    lot_number: inventoryLots[0].lot_number,
    quantity_delta: "2.000",
    balance_after: "6.000",
    created_at: stocktakePosted.posted_at,
  }],
} as const;

export const clinicStatuses = [
  ["NEW", "Новий", "#64748B", true, true, false],
  ["PENDING_CONFIRMATION", "Очікує підтвердження", "#F59E0B", true, true, false],
  ["CONFIRMED", "Підтверджено", "#2563EB", true, true, false],
  ["ARRIVED", "Пацієнт прийшов", "#7C3AED", true, true, true],
  ["IN_PROGRESS", "Прийом триває", "#0F766E", true, false, true],
  ["COMPLETED", "Завершено", "#16A34A", true, false, true],
  ["CANCELED", "Скасовано", "#DC2626", true, true, false],
  ["NO_SHOW", "Неявка", "#475569", true, true, false],
].map(([code, label, color, manualAdmin, manualReception, manualPodologist]) => ({
  code: code as string,
  label: label as string,
  color: color as string,
  manual_admin: manualAdmin as boolean,
  manual_reception: manualReception as boolean,
  manual_podologist: manualPodologist as boolean,
  version: 1,
  updated_at: "2026-07-21T12:00:00+03:00",
}));

export const clinicWorkdays = Array.from({ length: 7 }, (_, weekday) => ({
  weekday,
  is_working: weekday < 5,
  start_time: weekday < 5 ? "09:00" : null,
  end_time: weekday < 5 ? "18:00" : null,
  breaks: weekday < 5 ? [{
    id: `00000000-0000-4000-8000-00000000000${String(weekday)}`,
    start_time: "13:00",
    end_time: "14:00",
  }] : [],
  version: 1,
  updated_at: "2026-07-21T12:00:00+03:00",
}));

export const patientFixture = {
  id: "c49d72c2-689d-4f54-91df-9a63845a02e7",
  public_number: "P-C49D72C2689D",
  first_name: "Марія",
  last_name: "Бондар",
  display_name: "Марія Бондар",
  phone: "+380 67 123 45 67",
  birth_date: "1990-06-14",
  email: "maria@example.test",
  primary_podologist: null,
  appointment_summary: null,
  state_label: "Новий пацієнт",
  created_at: "2026-07-21T12:00:00+03:00",
} as const;

export const medicalPatientDetailFixture = {
  ...patientFixture,
  note: "Телефонувати після 16:00.",
  updated_at: "2026-07-21T12:00:00+03:00",
  age: 36,
  service_started_at: "2026-07-21T12:00:00+03:00",
  projection: "medical",
  upcoming_appointment: null,
  visit_history: [],
  medical_profile: {
    allergies: ["Латекс"],
    chronic_conditions: ["Цукровий діабет"],
    notes: "Контроль чутливості нігтьової пластини.",
    updated_at: "2026-07-21T12:00:00+03:00",
  },
  photo_archive: [],
} as const;

export const receptionPatientDetailFixture = {
  ...patientFixture,
  note: "Телефонувати після 16:00.",
  updated_at: "2026-07-21T12:00:00+03:00",
  age: 36,
  service_started_at: "2026-07-21T12:00:00+03:00",
  projection: "reception",
  upcoming_appointment: null,
  visit_history: [],
} as const;

export const workItemAssignees = [
  { id: 1, display_name: "Тест Адміністратор", role: "admin" },
  { id: 4, display_name: "Олена Подолог", role: "podologist" },
] as const;

export const workItemFixture = {
  id: "fe76f846-c0aa-4ee1-84e3-d9b91f0f3926",
  kind: "callback",
  kind_label: "Перетелефонувати",
  title: "Уточнити самопочуття після візиту",
  due_at: "2026-07-22T09:30:00+03:00",
  assignee: workItemAssignees[0],
  patient: {
    id: patientFixture.id,
    public_number: patientFixture.public_number,
    display_name: patientFixture.display_name,
    phone: patientFixture.phone,
  },
  comment: "Зателефонувати після 16:00.",
  is_important: true,
  is_completed: false,
  completed_at: null,
  completed_by: null,
  is_overdue: false,
  version: 1,
  created_by: workItemAssignees[0],
  created_at: "2026-07-21T12:00:00+03:00",
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

export const workItemListFixture = {
  work_items: [workItemFixture],
  summary: { open: 1, completed: 0, overdue: 0, important: 1 },
  assignees: workItemAssignees,
  effective_scope: "own",
} as const;

export const calendarFixture = {
  timezone: "Europe/Kyiv",
  range: {
    from: "2026-07-20T21:00:00Z",
    to: "2026-07-21T21:00:00Z",
  },
  specialists: [
    { id: 4, display_name: "Олена Подолог" },
    { id: 5, display_name: "Ірина Савчук" },
  ],
  days: [{
    date: "2026-07-21",
    is_working: true,
    starts_at: "2026-07-21T06:00:00Z",
    ends_at: "2026-07-21T15:00:00Z",
    breaks: [{
      starts_at: "2026-07-21T10:00:00Z",
      ends_at: "2026-07-21T11:00:00Z",
    }],
  }],
  events: [
    {
      id: "f41dff0b-2a0b-4f65-84bd-5a4455127825",
      public_number: "A-F41DFF0B2A0B",
      starts_at: "2026-07-21T06:30:00Z",
      ends_at: "2026-07-21T07:15:00Z",
      duration_minutes: 45,
      patient: {
        id: patientFixture.id,
        public_number: patientFixture.public_number,
        display_name: patientFixture.display_name,
      },
      service: { id: clinicService.id, name: clinicService.name, color: clinicService.color },
      specialist: { id: 4, display_name: "Олена Подолог" },
      room: { id: clinicRoom.id, name: clinicRoom.name },
      status: { code: "CONFIRMED", label: "Підтверджено", color: "#2563EB" },
    },
    {
      id: "3666acdb-a507-4984-842c-e2325557de0d",
      public_number: "A-3666ACDBA507",
      starts_at: "2026-07-21T06:30:00Z",
      ends_at: "2026-07-21T07:30:00Z",
      duration_minutes: 60,
      patient: {
        id: "a5dacb1f-bcab-4785-83e9-9ce6af32e52f",
        public_number: "P-A5DACB1FBCAB",
        display_name: "Ірина Коваль",
      },
      service: {
        id: "8487d46c-e741-4a09-bd3f-123c14fb4e21",
        name: "Обробка нігтів",
        color: "#7C3AED",
      },
      specialist: { id: 5, display_name: "Ірина Савчук" },
      room: {
        id: "e204d298-3bf3-4eca-b932-7a01dc7dbc89",
        name: "Кабінет 2",
      },
      status: { code: "NEW", label: "Новий", color: "#64748B" },
    },
  ],
} as const;

export const availabilityFixture = {
  timezone: "Europe/Kyiv",
  date: "2026-07-21",
  specialist: calendarFixture.specialists[0],
  service: {
    id: clinicService.id,
    name: clinicService.name,
    duration_minutes: clinicService.duration_minutes,
  },
  requested_room: null,
  step_minutes: 15,
  slots: [
    {
      starts_at: "2026-07-21T08:00:00Z",
      ends_at: "2026-07-21T08:45:00Z",
      rooms: [{ id: clinicRoom.id, name: clinicRoom.name }],
    },
    {
      starts_at: "2026-07-21T08:15:00Z",
      ends_at: "2026-07-21T09:00:00Z",
      rooms: [{ id: clinicRoom.id, name: clinicRoom.name }],
    },
  ],
} as const;

export const appointmentFixture = {
  id: "18dc9769-4dc6-4f5e-884a-b47844c2054e",
  public_number: "A-18DC97694DC6",
  starts_at: availabilityFixture.slots[0].starts_at,
  ends_at: availabilityFixture.slots[0].ends_at,
  duration_minutes: clinicService.duration_minutes,
  patient: {
    id: patientFixture.id,
    public_number: patientFixture.public_number,
    display_name: patientFixture.display_name,
    phone: patientFixture.phone,
  },
  service: {
    id: clinicService.id,
    code: clinicService.code,
    name: clinicService.name,
    color: clinicService.color,
  },
  specialist: calendarFixture.specialists[0],
  room: { id: clinicRoom.id, name: clinicRoom.name },
  status: { code: "NEW", label: "Новий", color: "#64748B" },
  complaints: "Біль під час ходьби",
  has_no_complaints: false,
  comment: "",
  cancellation_reason: "",
  version: 1,
  created_at: "2026-07-21T07:45:00Z",
  updated_at: "2026-07-21T07:45:00Z",
} as const;

export const appointmentDetailFixture = {
  ...appointmentFixture,
  id: calendarFixture.events[0].id,
  public_number: calendarFixture.events[0].public_number,
  starts_at: calendarFixture.events[0].starts_at,
  ends_at: calendarFixture.events[0].ends_at,
  status: calendarFixture.events[0].status,
  comment: "Нагадати про домашній догляд",
  version: 4,
  allowed_status_transitions: [
    { code: "ARRIVED", label: "Пацієнт прийшов", color: "#7C3AED" },
  ],
  can_edit: true,
  can_reschedule: true,
  can_cancel: true,
  can_start_visit: false,
  visit_id: null,
} as const;

export const arrivedAppointmentDetailFixture = {
  ...appointmentDetailFixture,
  status: { code: "ARRIVED", label: "Пацієнт прийшов", color: "#7C3AED" },
  version: 5,
  allowed_status_transitions: [],
  can_start_visit: true,
} as const;

export const visitFixture = {
  id: "28b23340-407f-4d3b-bced-0b771f80af15",
  public_number: "V-28B23340407F",
  status: "DRAFT",
  version: 1,
  appointment: {
    id: arrivedAppointmentDetailFixture.id,
    public_number: arrivedAppointmentDetailFixture.public_number,
    starts_at: arrivedAppointmentDetailFixture.starts_at,
    ends_at: arrivedAppointmentDetailFixture.ends_at,
    service_name: arrivedAppointmentDetailFixture.service.name,
    room_name: arrivedAppointmentDetailFixture.room.name,
    status_code: "IN_PROGRESS",
    status_label: "Прийом триває",
  },
  patient: {
    id: arrivedAppointmentDetailFixture.patient.id,
    public_number: arrivedAppointmentDetailFixture.patient.public_number,
    display_name: arrivedAppointmentDetailFixture.patient.display_name,
  },
  specialist: arrivedAppointmentDetailFixture.specialist,
  complaints: arrivedAppointmentDetailFixture.complaints,
  has_no_complaints: false,
  objective_examination: "",
  detected_conditions: [],
  podologist_notes: "",
  total_minor: null,
  payment_handoff_requested: false,
  service_lines: [{
    id: "a8683212-6a31-4c9f-89eb-76a148025eb3",
    service_id: clinicService.id,
    service_code: clinicService.code,
    service_name: clinicService.name,
    duration_minutes: clinicService.duration_minutes,
    price_minor: clinicService.price_minor,
    quantity: 1,
    is_primary: true,
    line_total_minor: clinicService.price_minor,
  }],
  material_lines: [],
  services_total_minor: clinicService.price_minor,
  photos: [],
  recommendations: [],
  editable: true,
  started_at: "2026-07-21T08:05:00Z",
  updated_at: "2026-07-21T08:05:00Z",
  completed_at: null,
} as const;

export const visitPhotoBeforeFixture = {
  id: "7b97276c-7eed-4894-a8ca-523181355bc7",
  visit_id: visitFixture.id,
  kind: "BEFORE",
  content_type: "image/jpeg",
  size: 48_120,
  width: 1280,
  height: 960,
  original_name: "before-procedure.jpg",
  preview_status: "READY",
  created_by_id: adminSession.user.id,
  created_by_name: adminSession.user.display_name,
  created_at: "2026-07-21T08:12:00Z",
  image_url: "/api/v1/visit-photo-content?token=before-original",
  preview_url: "/api/v1/visit-photo-content?token=before-preview",
} as const;

export const visitPhotoAfterFixture = {
  ...visitPhotoBeforeFixture,
  id: "82c61900-f250-4f99-94e4-96ee3d6167d6",
  kind: "AFTER",
  original_name: "after-procedure.webp",
  content_type: "image/webp",
  size: 39_450,
  preview_status: "PROCESSING",
  created_at: "2026-07-21T08:32:00Z",
  image_url: "/api/v1/visit-photo-content?token=after-original",
  preview_url: null,
} as const;

export const patientHistoryVisitFixture = {
  id: visitFixture.id,
  public_number: visitFixture.public_number,
  occurred_at: "2026-07-21T08:00:00Z",
  completed_at: "2026-07-21T09:00:00Z",
  status: "COMPLETED",
  status_label: "Завершено",
  services: [{
    service_name: clinicService.name,
    quantity: 1,
    line_total_minor: clinicService.price_minor,
  }],
  specialist: { id: 4, display_name: "Олена Подолог" },
  total_minor: clinicService.price_minor,
  clinical_summary: "Шкіра спокійна, загоєння без ускладнень.",
  has_photos: true,
  before_photo_count: 1,
  after_photo_count: 1,
  recommendations_count: 1,
} as const;

export const patientHistoryResponseFixture = {
  visits: [patientHistoryVisitFixture],
  next_cursor: null,
} as const;

export const patientPhotoArchiveResponseFixture = {
  visits: [{
    id: visitFixture.id,
    public_number: visitFixture.public_number,
    occurred_at: patientHistoryVisitFixture.occurred_at,
    completed_at: patientHistoryVisitFixture.completed_at,
    status: patientHistoryVisitFixture.status,
    status_label: patientHistoryVisitFixture.status_label,
    services: patientHistoryVisitFixture.services,
    specialist: patientHistoryVisitFixture.specialist,
    total_minor: patientHistoryVisitFixture.total_minor,
    photos: [visitPhotoBeforeFixture, visitPhotoAfterFixture],
  }],
  next_cursor: null,
} as const;

export const patientRecommendationFixture = {
  id: "1c1e09f8-b7f1-4b4a-aa0b-6eeeb4f84ac7",
  visit: {
    id: visitFixture.id,
    public_number: visitFixture.public_number,
    occurred_at: patientHistoryVisitFixture.occurred_at,
    services: [clinicService.name],
  },
  author: { id: 4, display_name: "Олена Подолог" },
  text: "Обробляти ділянку двічі на день та уникати тиску.",
  version: 1,
  created_at: "2026-07-21T09:00:00Z",
  updated_at: "2026-07-21T09:00:00Z",
  can_edit: true,
} as const;

export const patientRecommendationResponseFixture = {
  recommendations: [patientRecommendationFixture],
  eligible_visits: [patientRecommendationFixture.visit],
  next_cursor: null,
} as const;

export const visitMaterialOptions = {
  materials: [{
    id: inventoryMaterial.id,
    sku: inventoryMaterial.sku,
    name: inventoryMaterial.name,
    unit: inventoryMaterial.unit,
    available_quantity: inventoryMaterial.available_quantity,
    lots: inventoryLots.map((lot) => ({
      id: lot.id,
      lot_number: lot.lot_number,
      expires_on: lot.expires_on,
      current_quantity: lot.current_quantity,
      fefo_rank: lot.fefo_rank,
    })),
  }],
} as const;

export const cashShiftFixture = {
  id: "840f933c-5a86-468a-8862-010166bca112",
  public_number: "CS-20260722-0001",
  status: "OPEN",
  employee: {
    id: 1,
    name: "Тест Адміністратор",
    email: "admin@example.test",
    role: "admin",
  },
  opened_at: "2026-07-22T07:15:00Z",
  totals: {
    operations_count: 2,
    payment_count: 1,
    refund_count: 0,
    payments_total_minor: 250000,
    refunds_total_minor: 0,
    revenue_minor: 250000,
    cash_payments_minor: 0,
    cash_refunds_minor: 0,
    card_payments_minor: 250000,
    card_refunds_minor: 0,
    transfer_payments_minor: 0,
    transfer_refunds_minor: 0,
    deposits_minor: 50000,
    withdrawals_minor: 0,
    expected_cash_minor: 50000,
  },
  entries: [
    {
      id: "9ae14bc4-0dce-4aed-8132-a325883ea44b",
      public_number: "CASH-000002",
      kind: "PAYMENT",
      amount_minor: 250000,
      payment_method: "CARD",
      actor_id: 1,
      actor_name: "Тест Адміністратор",
      actor_email: "admin@example.test",
      posted_at: "2026-07-22T09:15:00Z",
    },
    {
      id: "6f2bcda2-ec84-4db6-8b53-a7c11e93df17",
      public_number: "CASH-000001",
      kind: "DEPOSIT",
      amount_minor: 50000,
      payment_method: null,
      actor_id: 2,
      actor_name: "Тест Рецепція",
      actor_email: "reception@example.test",
      posted_at: "2026-07-22T07:00:00Z",
    },
  ],
} as const;

export const emptyCashShiftFixture = {
  ...cashShiftFixture,
  id: "d3fb45e4-75b9-407d-aa88-b393dd24d865",
  public_number: "CS-20260722-0002",
  totals: Object.fromEntries(
    Object.keys(cashShiftFixture.totals).map((key) => [key, 0]),
  ) as Record<keyof typeof cashShiftFixture.totals, number>,
  entries: [],
};

export const financeOpenOperation = {
  id: "70110000-0000-4000-8000-000000000001",
  type: "PAYMENT",
  status: "OPEN",
  occurred_at: "2026-07-22T10:30:00Z",
  amount_minor: 135000,
  patient: {
    id: patientFixture.id,
    public_number: patientFixture.public_number,
    display_name: patientFixture.display_name,
    phone: patientFixture.phone,
  },
  visit: {
    id: "70120000-0000-4000-8000-000000000001",
    public_number: "VIS-701200000000",
    completed_at: "2026-07-22T10:30:00Z",
    payment_handoff_requested: true,
    total_minor: 135000,
    specialist: { id: 4, name: "Олена Подолог" },
    services: [
      {
        id: "70130000-0000-4000-8000-000000000001",
        code: "PEDICURE",
        name: "Медичний педикюр",
        quantity: 1,
        unit_price_minor: 95000,
        line_total_minor: 95000,
      },
      {
        id: "70130000-0000-4000-8000-000000000002",
        code: "CONSULT",
        name: "Консультація подолога",
        quantity: 1,
        unit_price_minor: 40000,
        line_total_minor: 40000,
      },
    ],
  },
  payment: null,
  refund: null,
} as const;

export const financePaidOperation = {
  ...financeOpenOperation,
  id: "70110000-0000-4000-8000-000000000002",
  status: "PAID",
  occurred_at: "2026-07-22T09:15:00Z",
  amount_minor: 250000,
  patient: {
    id: "70140000-0000-4000-8000-000000000002",
    public_number: "PAT-701400000000",
    display_name: "Наталія Коваль",
    phone: "+380 67 234 56 78",
  },
  visit: {
    ...financeOpenOperation.visit,
    id: "70120000-0000-4000-8000-000000000002",
    public_number: "VIS-701200000002",
    completed_at: "2026-07-22T09:00:00Z",
    total_minor: 250000,
    specialist: { id: 5, name: "Ірина Романюк" },
    services: [{
      id: "70130000-0000-4000-8000-000000000003",
      code: "ORTHONYXIA",
      name: "Корекційна система",
      quantity: 1,
      unit_price_minor: 250000,
      line_total_minor: 250000,
    }],
  },
  payment: {
    id: "70150000-0000-4000-8000-000000000001",
    ledger_entry_id: cashShiftFixture.entries[0].id,
    public_number: cashShiftFixture.entries[0].public_number,
    payment_method: "CARD",
    comment: "Оплату підтверджено на терміналі.",
    posted_at: "2026-07-22T09:15:00Z",
    actor: { id: 1, name: "Тест Адміністратор" },
    cash_shift: { id: cashShiftFixture.id, public_number: cashShiftFixture.public_number },
  },
  refund: null,
} as const;

export const financeZeroOperation = {
  ...financeOpenOperation,
  id: "70110000-0000-4000-8000-000000000003",
  status: "PAID",
  occurred_at: "2026-07-22T08:30:00Z",
  amount_minor: 0,
  patient: {
    id: "70140000-0000-4000-8000-000000000003",
    public_number: "PAT-701400000003",
    display_name: "Олег Петренко",
    phone: "+380 67 901 34 27",
  },
  visit: {
    ...financeOpenOperation.visit,
    id: "70120000-0000-4000-8000-000000000003",
    public_number: "VIS-701200000003",
    completed_at: "2026-07-22T08:30:00Z",
    total_minor: 0,
    services: [],
  },
  payment: null,
  refund: null,
} as const;

export const financeRefund = {
  id: "70350000-0000-4000-8000-000000000001",
  ledger_entry_id: "70360000-0000-4000-8000-000000000001",
  public_number: "TXN-703600000001",
  reason: "Послугу скасовано за погодженням із пацієнтом.",
  posted_at: "2026-07-22T11:30:00Z",
  actor: { id: 1, name: "Тест Адміністратор" },
  cash_shift: { id: cashShiftFixture.id, public_number: cashShiftFixture.public_number },
} as const;

export const financeRefundedPaymentOperation = {
  ...financePaidOperation,
  id: "70310000-0000-4000-8000-000000000001",
  status: "REFUNDED",
  patient: {
    id: "70340000-0000-4000-8000-000000000001",
    public_number: "PAT-703400000001",
    display_name: "Олександр Левченко",
    phone: "+380 68 445 09 91",
  },
  visit: {
    ...financePaidOperation.visit,
    id: "70320000-0000-4000-8000-000000000001",
    public_number: "VIS-703200000001",
  },
  payment: {
    ...financePaidOperation.payment,
    id: "70350000-0000-4000-8000-000000000002",
    ledger_entry_id: "70360000-0000-4000-8000-000000000002",
    public_number: "TXN-703600000002",
  },
  refund: financeRefund,
} as const;

export const financeRefundOperation = {
  id: financeRefund.id,
  type: "REFUND",
  status: "POSTED",
  occurred_at: financeRefund.posted_at,
  amount_minor: financeRefundedPaymentOperation.amount_minor,
  patient: financeRefundedPaymentOperation.patient,
  visit: financeRefundedPaymentOperation.visit,
  original_payment: financeRefundedPaymentOperation.payment,
  refund: financeRefund,
} as const;

export const financeCrossShiftRefundOperation = {
  ...financeRefundOperation,
  id: "70350000-0000-4000-8000-000000000011",
  original_payment: {
    ...financeRefundOperation.original_payment,
    id: "70350000-0000-4000-8000-000000000012",
    ledger_entry_id: "70360000-0000-4000-8000-000000000012",
    public_number: "TXN-703600000012",
    actor: { id: 5, name: "Ірина Романюк" },
    cash_shift: {
      id: "70380000-0000-4000-8000-000000000012",
      public_number: "CS-20260721-0042",
    },
  },
  refund: {
    ...financeRefundOperation.refund,
    id: "70350000-0000-4000-8000-000000000011",
    ledger_entry_id: "70360000-0000-4000-8000-000000000011",
    public_number: "TXN-703600000011",
    actor: { id: 1, name: "Тест Адміністратор" },
    cash_shift: { id: cashShiftFixture.id, public_number: cashShiftFixture.public_number },
  },
} as const;

export const financeDepositOperation = {
  id: "70370000-0000-4000-8000-000000000001",
  type: "DEPOSIT",
  status: "POSTED",
  occurred_at: "2026-07-22T11:15:00Z",
  amount_minor: 30000,
  cash_adjustment: {
    id: "70370000-0000-4000-8000-000000000001",
    ledger_entry_id: "70360000-0000-4000-8000-000000000003",
    public_number: "TXN-703600000003",
    reason: "Розмінні кошти",
    comment: "Внесення на початок другої половини дня.",
    posted_at: "2026-07-22T11:15:00Z",
    actor: { id: 1, name: "Тест Адміністратор" },
    cash_shift: { id: cashShiftFixture.id, public_number: cashShiftFixture.public_number },
  },
} as const;

export const financeWithdrawalOperation = {
  ...financeDepositOperation,
  id: "70370000-0000-4000-8000-000000000002",
  type: "WITHDRAWAL",
  occurred_at: "2026-07-22T11:20:00Z",
  amount_minor: 20000,
  cash_adjustment: {
    ...financeDepositOperation.cash_adjustment,
    id: "70370000-0000-4000-8000-000000000002",
    ledger_entry_id: "70360000-0000-4000-8000-000000000004",
    public_number: "TXN-703600000004",
    reason: "Інкасація",
    comment: "",
    posted_at: "2026-07-22T11:20:00Z",
  },
} as const;

export const financeOperationsFixture = {
  operations: [financeOpenOperation, financePaidOperation, financeZeroOperation, financeRefundedPaymentOperation, financeRefundOperation, financeDepositOperation, financeWithdrawalOperation],
  next_cursor: null,
} as const;

export const globalSearchFixture = {
  query: "Марія",
  groups: [
    {
      type: "patients",
      has_more: false,
      items: [{
        type: "patient",
        id: patientFixture.id,
        title: patientFixture.display_name,
        subtitle: `${patientFixture.phone} · ${patientFixture.public_number}`,
        meta: "Картка пацієнта",
        deep_link: `/patients/${patientFixture.id}/overview`,
      }],
    },
    {
      type: "appointments",
      has_more: false,
      items: [{
        type: "appointment",
        id: appointmentDetailFixture.id,
        title: `${appointmentDetailFixture.patient.display_name} · 09:00`,
        subtitle: `${appointmentDetailFixture.service.name} · ${appointmentDetailFixture.specialist.display_name}`,
        meta: appointmentDetailFixture.public_number,
        deep_link: `/calendar?appointment=${appointmentDetailFixture.id}`,
      }],
    },
    {
      type: "payments",
      has_more: false,
      items: [{
        type: "payment",
        id: financePaidOperation.id,
        title: `${financePaidOperation.patient.display_name} · оплата`,
        subtitle: financePaidOperation.payment.public_number,
        meta: financePaidOperation.visit.public_number,
        deep_link: `/finance?operation=PAYMENT:${financePaidOperation.id}`,
      }],
    },
    {
      type: "materials",
      has_more: false,
      items: [{
        type: "material",
        id: inventoryMaterial.id,
        title: inventoryMaterial.name,
        subtitle: `ART ${inventoryMaterial.sku}`,
        meta: "Низький залишок",
        deep_link: `/inventory?material=${inventoryMaterial.id}`,
      }],
    },
  ],
  returned_count: 4,
} as const;

export const financePaymentResult = {
  operation: {
    ...financeOpenOperation,
    status: "PAID",
    occurred_at: "2026-07-22T10:45:00Z",
    payment: {
      id: "70150000-0000-4000-8000-000000000002",
      ledger_entry_id: "70160000-0000-4000-8000-000000000002",
      public_number: "TXN-701600000000",
      payment_method: "CARD",
      comment: "Повна оплата",
      posted_at: "2026-07-22T10:45:00Z",
      actor: { id: 1, name: "Тест Адміністратор" },
      cash_shift: { id: cashShiftFixture.id, public_number: cashShiftFixture.public_number },
    },
  },
  replayed: false,
} as const;

export const financeRefundResult = {
  operation: financeRefundOperation,
  replayed: false,
} as const;

export const financeDepositResult = {
  operation: financeDepositOperation,
  replayed: false,
} as const;

export const financeWithdrawalResult = {
  operation: financeWithdrawalOperation,
  replayed: false,
} as const;

export const notificationFixture = {
  id: "6740940b-0aad-48e1-a142-8333bca113a9",
  kind: "appointment_arrived",
  title: "Пацієнт уже прибув",
  message: "Марія Бондар очікує на прийом о 22.07.2026, 12:00.",
  tone: "sage",
  is_important: true,
  deep_link: "/calendar?appointment=e18dc976-94dc-4f6a-bf66-57139bea10fa",
  occurred_at: "2026-07-22T08:55:00Z",
  created_at: "2026-07-22T08:55:01Z",
  read_at: null,
  is_read: false,
} as const;

export const notificationListFixture = {
  notifications: [notificationFixture],
  total_count: 1,
  unread_count: 1,
  next_cursor: null,
} as const;

export const auditEventFixture = {
  id: "80300000-0000-4000-8000-000000000001",
  occurred_at: "2026-07-22T11:18:00Z",
  actor: {
    id: 1,
    display_name: "Тест Адміністратор",
    email: "admin@example.test",
    role: "admin",
  },
  section: "scheduling",
  action: "scheduling.appointment_canceled",
  object: {
    type: "appointment",
    id: appointmentFixture.id,
    label: `${appointmentFixture.patient.display_name} · ${appointmentFixture.public_number}`,
  },
  result: "success",
  description: "Запис скасовано за проханням пацієнта.",
} as const;

export const auditEventDetailFixture = {
  ...auditEventFixture,
  before: { status: "CONFIRMED", cancellation_reason: "" },
  after: { status: "CANCELED", cancellation_reason: "Пацієнт не може прийти" },
  changes: [
    { field: "cancellation_reason", before: "", after: "Пацієнт не може прийти" },
    { field: "status", before: "CONFIRMED", after: "CANCELED" },
  ],
  note: "Потрібно запропонувати новий час.",
  correlation_id: "tp-803-test-event",
} as const;

export const auditEventListFixture = {
  events: [auditEventFixture],
  next_cursor: null,
} as const;

export const overviewFixture = {
  role: "admin",
  date: "2026-07-22",
  timezone: "Europe/Kyiv",
  metrics: [
    { key: "appointments", label: "Записи кабінету", value: 8, format: "integer", note: "без скасованих", tone: "sage" },
    { key: "expected_income_minor", label: "Очікуваний дохід", value: 145000, format: "money", note: "за цінами каталогу", tone: "sand" },
    { key: "specialists", label: "Спеціалісти", value: 2, format: "integer", note: "у розкладі", tone: "lilac" },
    { key: "attention", label: "Потребує уваги", value: 1, format: "integer", note: "справи, доступ і оплати", tone: "coral" },
  ],
  schedule: [
    {
      id: appointmentFixture.id,
      public_number: appointmentFixture.public_number,
      starts_at: "2026-07-22T09:30:00+03:00",
      ends_at: "2026-07-22T10:15:00+03:00",
      duration_minutes: 45,
      patient: {
        id: appointmentFixture.patient.id,
        public_number: appointmentFixture.patient.public_number,
        display_name: appointmentFixture.patient.display_name,
      },
      specialist: { id: 4, display_name: "Олена Подолог" },
      service: { id: clinicService.id, name: clinicService.name, color: clinicService.color },
      room: { id: clinicRoom.id, name: clinicRoom.name },
      status: { code: "CONFIRMED", label: "Підтверджено", color: "#0F766E" },
    },
  ],
  next_appointment: {
    id: appointmentFixture.id,
    public_number: appointmentFixture.public_number,
    starts_at: "2026-07-22T09:30:00+03:00",
    ends_at: "2026-07-22T10:15:00+03:00",
    duration_minutes: 45,
    patient: {
      id: appointmentFixture.patient.id,
      public_number: appointmentFixture.patient.public_number,
      display_name: appointmentFixture.patient.display_name,
    },
    specialist: { id: 4, display_name: "Олена Подолог" },
    service: { id: clinicService.id, name: clinicService.name, color: clinicService.color },
    room: { id: clinicRoom.id, name: clinicRoom.name },
    status: { code: "CONFIRMED", label: "Підтверджено", color: "#0F766E" },
  },
  workday: {
    is_working: true,
    starts_at: "2026-07-22T09:00:00+03:00",
    ends_at: "2026-07-22T18:00:00+03:00",
    break_minutes: 30,
    net_minutes: 510,
  },
  attention: [
    { kind: "work_items", label: "Прострочені або важливі справи", count: 1, deep_link: "/work-items" },
  ],
} as const;

export const analyticsFixture = {
  period: { date_from: "2026-07-01", date_to: "2026-07-31", timezone: "Europe/Kyiv", bucket: "day" },
  filters: { specialist: null, service: null },
  available_specialists: [{ id: "4", name: "Олена Подолог", is_active: true }],
  available_services: [{ id: clinicService.id, name: clinicService.name, is_active: true }],
  kpis: {
    completed_visits: 24,
    revenue_minor: 2845000,
    payment_count: 23,
    average_check_minor: 123696,
    returning_patient_rate_bps: 6250,
    returning_patients: 15,
    served_patients: 24,
    new_patients: 9,
    canceled_appointments: 3,
    no_show_appointments: 2,
    average_return_interval_days: 31,
  },
  trend: [
    { date_from: "2026-07-01", date_to: "2026-07-01", label: "01.07", visits: 8, revenue_minor: 920000 },
    { date_from: "2026-07-02", date_to: "2026-07-02", label: "02.07", visits: 6, revenue_minor: 780000 },
    { date_from: "2026-07-03", date_to: "2026-07-03", label: "03.07", visits: 10, revenue_minor: 1145000 },
  ],
  appointment_outcomes: [
    { code: "COMPLETED", label: "Завершено", count: 24 },
    { code: "CANCELED", label: "Скасовано", count: 3 },
    { code: "NO_SHOW", label: "Неявки", count: 2 },
    { code: "OTHER", label: "Інші", count: 4 },
  ],
  specialist_performance: [
    { id: 4, name: "Олена Подолог", is_active: true, completed_visits: 24, scheduled_minutes: 1620, available_minutes: 7920, utilization_bps: 2045, revenue_minor: 2845000 },
  ],
  service_ranking: [
    { id: clinicService.id, code: clinicService.code, name: clinicService.name, visit_count: 18, quantity: 20, billed_total_minor: 2400000 },
  ],
} as const;

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:inventory-export"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(),
  });
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/auth/logout") && method === "POST") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (new URL(url).pathname === "/api/v1/overview" && method === "GET") {
        return Promise.resolve(jsonResponse(overviewFixture));
      }
      if (new URL(url).pathname === "/api/v1/analytics" && method === "GET") {
        return Promise.resolve(jsonResponse(analyticsFixture));
      }
      if (url.includes("/api/v1/users") && method === "GET") {
        return Promise.resolve(jsonResponse({ users: [] }));
      }
      if (/\/api\/v1\/audit-events\/[0-9a-f-]+$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(auditEventDetailFixture));
      }
      if (new URL(url).pathname === "/api/v1/audit-events" && method === "GET") {
        return Promise.resolve(jsonResponse(auditEventListFixture));
      }
      if (new URL(url).pathname === "/api/v1/notifications" && method === "GET") {
        return Promise.resolve(jsonResponse({
          notifications: [],
          total_count: 0,
          unread_count: 0,
          next_cursor: null,
        }));
      }
      if (url.includes("/api/v1/clinic-profile") && method === "GET") {
        return Promise.resolve(jsonResponse(clinicProfile));
      }
      if (url.includes("/api/v1/rooms") && method === "GET") {
        return Promise.resolve(jsonResponse({ rooms: [clinicRoom] }));
      }
      if (url.includes("/api/v1/services") && method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      if (url.includes("/api/v1/appointment-status-configs") && method === "GET") {
        return Promise.resolve(jsonResponse({ statuses: clinicStatuses }));
      }
      if (url.includes("/api/v1/clinic-workdays") && method === "GET") {
        return Promise.resolve(jsonResponse({ timezone: "Europe/Kyiv", workdays: clinicWorkdays }));
      }
      if (url.includes("/api/v1/inventory/suppliers") && method === "GET") {
        return Promise.resolve(jsonResponse({ suppliers: [inventorySupplier, inactiveInventorySupplier] }));
      }
      if (url.includes(`/api/v1/inventory/materials/${inventoryMaterial.id}/lots`) && method === "GET") {
        return Promise.resolve(jsonResponse({ lots: inventoryLots }));
      }
      if (url.includes(`/api/v1/inventory/materials/${inventoryMaterial.id}`) && method === "GET") {
        return Promise.resolve(jsonResponse(inventoryMaterial));
      }
      if (url.includes("/api/v1/inventory/materials") && method === "GET") {
        return Promise.resolve(jsonResponse({ materials: [inventoryMaterial, healthyInventoryMaterial] }));
      }
      if (url.includes("/api/v1/inventory/stocktakes/preview") && method === "GET") {
        return Promise.resolve(jsonResponse(stocktakePreview));
      }
      if (url.includes(`/api/v1/inventory/operations/${stocktakeOperationDetail.id}`) && method === "GET") {
        return Promise.resolve(jsonResponse(stocktakeOperationDetail));
      }
      if (url.includes("/api/v1/inventory/movements/export") && method === "GET") {
        return Promise.resolve(new Response(
          "posted_at_local,operation_number\r\n2026-07-23T10:00:00+03:00,INV-TEST-001\r\n",
          {
            status: 200,
            headers: {
              "Content-Type": "text/csv; charset=utf-8",
              "Content-Disposition": "attachment; filename=\"inventory-movements-20260723-100000.csv\"",
              "X-Export-Row-Count": "1",
            },
          },
        ));
      }
      if (url.includes("/api/v1/inventory/movements") && method === "GET") {
        return Promise.resolve(jsonResponse(inventoryMovementJournal));
      }
      if (/\/api\/v1\/finance\/operations\/PAYMENT\/[0-9a-f-]+$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(financePaidOperation));
      }
      if (url.includes("/api/v1/finance/operations") && method === "GET") {
        const params = new URL(url).searchParams;
        const status = params.get("status");
        const type = params.get("type");
        if (params.get("refundable_only") === "true") return Promise.resolve(jsonResponse({ operations: [financePaidOperation], next_cursor: null }));
        if (status === "OPEN") return Promise.resolve(jsonResponse({ operations: [financeOpenOperation], next_cursor: null }));
        if (type !== null) return Promise.resolve(jsonResponse({ operations: financeOperationsFixture.operations.filter((operation) => operation.type === type), next_cursor: null }));
        return Promise.resolve(jsonResponse(financeOperationsFixture));
      }
      if (url.endsWith("/api/v1/payments") && method === "POST") {
        return Promise.resolve(jsonResponse(financePaymentResult, 201));
      }
      if (/\/api\/v1\/payments\/[0-9a-f-]+\/refunds$/.test(new URL(url).pathname) && method === "POST") {
        return Promise.resolve(jsonResponse(financeRefundResult, 201));
      }
      if (url.endsWith("/api/v1/cash-movements") && method === "POST") {
        const body = input instanceof Request ? input.clone() : new Request(input, init).clone();
        return body.json().then((payload: { type?: string }) => jsonResponse(payload.type === "WITHDRAWAL" ? financeWithdrawalResult : financeDepositResult, 201));
      }
      if (url.includes("/api/v1/cash-shifts/current") && method === "GET") {
        return Promise.resolve(jsonResponse({ shift: cashShiftFixture }));
      }
      if (url.endsWith("/api/v1/cash-shifts") && method === "POST") {
        return Promise.resolve(jsonResponse(emptyCashShiftFixture, 201));
      }
      if (url.includes("/api/v1/work-items") && method === "GET") {
        return Promise.resolve(jsonResponse(workItemListFixture));
      }
      if (url.includes("/api/v1/calendar") && method === "GET") {
        return Promise.resolve(jsonResponse(calendarFixture));
      }
      if (url.includes("/api/v1/appointments/availability") && method === "GET") {
        return Promise.resolve(jsonResponse(availabilityFixture));
      }
      if (/\/api\/v1\/visits\/[0-9a-f-]+$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(visitFixture));
      }
      if (/\/api\/v1\/visits\/[0-9a-f-]+\/material-options$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(visitMaterialOptions));
      }
      if (/\/api\/v1\/visits\/[0-9a-f-]+$/.test(new URL(url).pathname) && method === "PUT") {
        return Promise.resolve(jsonResponse({ ...visitFixture, version: visitFixture.version + 1 }));
      }
      if (/\/api\/v1\/appointments\/[0-9a-f-]+$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(appointmentDetailFixture));
      }
      if (url.includes("/start-visit") && method === "POST") {
        return Promise.resolve(jsonResponse(visitFixture, 201));
      }
      if (url.includes("/api/v1/appointments") && method === "POST") {
        return Promise.resolve(jsonResponse(appointmentFixture, 201));
      }
      if (/\/api\/v1\/patients\/[0-9a-f-]+\/visits$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(patientHistoryResponseFixture));
      }
      if (/\/api\/v1\/patients\/[0-9a-f-]+\/photos$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(patientPhotoArchiveResponseFixture));
      }
      if (/\/api\/v1\/patients\/[0-9a-f-]+\/recommendations$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(patientRecommendationResponseFixture));
      }
      if (/\/api\/v1\/patients\/[0-9a-f-]+$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(medicalPatientDetailFixture));
      }
      if (url.includes("/api/v1/patients") && method === "GET") {
        return Promise.resolve(jsonResponse({ patients: [patientFixture], next_cursor: null }));
      }
      if (url.includes("/api/v1/patients") && method === "POST") {
        return Promise.resolve(jsonResponse({
          patient: medicalPatientDetailFixture,
          duplicate_warning: false,
          possible_duplicates: [],
        }, 201));
      }
      if (url.includes("/api/v1/search") && method === "GET") {
        return Promise.resolve(jsonResponse(globalSearchFixture));
      }
      return Promise.resolve(jsonResponse(adminSession));
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
