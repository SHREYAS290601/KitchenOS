const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export type Health = { status: string; service: string };

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: "unreachable" | "unhealthy" };

export type SourcedFieldPayload = {
  value: string | number | null;
  source: string;
  confidence: number;
  status: string;
};

export type PantryItemPayload = {
  pantry_item_id: string;
  user_id: string;
  canonical_name: SourcedFieldPayload | null;
  display_name: SourcedFieldPayload | null;
  category: SourcedFieldPayload | null;
  brand: SourcedFieldPayload | null;
  product_name: SourcedFieldPayload | null;
  quantity_value: SourcedFieldPayload | null;
  quantity_type: string;
  unit_label: string | null;
  purchase_date: string | null;
  storage_location: string | null;
  estimated_use_by: string | null;
  status: string;
  needs_user_review: boolean;
};

export type FieldActionName = "confirm" | "edit" | "reject" | "leave_as_estimate";

export type FieldActionResult =
  | { ok: true; outcome: string; field: SourcedFieldPayload | null }
  | { ok: false; message: string };

export async function getPantryItem(
  itemId: string,
): Promise<ApiResult<PantryItemPayload>> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/pantry/items/${itemId}`);
  } catch {
    return { ok: false, error: "unreachable" };
  }
  if (!response.ok) {
    return { ok: false, error: "unhealthy" };
  }
  const data = (await response.json()) as PantryItemPayload;
  return { ok: true, data };
}

export async function postFieldAction(
  itemId: string,
  fieldName: string,
  action: FieldActionName,
  value?: string | number | null,
): Promise<FieldActionResult> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/pantry/items/${itemId}/fields/${fieldName}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(action === "edit" ? { action, value } : { action }),
    });
  } catch {
    return { ok: false, message: `Could not reach the server to update ${fieldName}` };
  }
  const body = (await response.json()) as {
    outcome?: string;
    field?: SourcedFieldPayload | null;
    detail?: string;
  };
  if (!response.ok) {
    return { ok: false, message: body.detail ?? `Updating ${fieldName} failed` };
  }
  return { ok: true, outcome: body.outcome ?? "applied", field: body.field ?? null };
}

export async function getHealth(): Promise<ApiResult<Health>> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/healthz`);
  } catch {
    return { ok: false, error: "unreachable" };
  }
  if (!response.ok) {
    return { ok: false, error: "unhealthy" };
  }
  const data = (await response.json()) as Health;
  return { ok: true, data };
}
