import type { components } from "./api/schema";

export type ContractSuccess = components["schemas"]["ContractFixture"];
export type ErrorEnvelope = components["schemas"]["ErrorEnvelope"];

export const successFixture = {
  status: "ok",
  message: "API contract is available.",
  correlation_id: "tp102-story-success",
} satisfies ContractSuccess;

export const errorFixture = {
  code: "validation_error",
  message: "Дані запиту не пройшли перевірку.",
  fields: {
    outcome: ["Allowed values: success, error."],
  },
  correlation_id: "tp102-story-error",
} satisfies ErrorEnvelope;
