import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY = "checklist.v1";
const PENDING_KEY = "checklist.pending.v1";

export type ChecklistItem = {
  id: string;
  name: string;
  checked: boolean;
  category?: string;
  status?: "planned" | "bought";
};

export async function saveChecklist(items: ChecklistItem[]): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(items));
}

export async function loadChecklist(): Promise<ChecklistItem[] | null> {
  const raw = await AsyncStorage.getItem(KEY);
  if (raw === null) {
    return null;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ChecklistItem[]) : null;
  } catch {
    return null;
  }
}

export async function clearChecklist(): Promise<void> {
  await AsyncStorage.removeItem(KEY);
}

export async function loadPendingCrossOffs(): Promise<string[]> {
  const raw = await AsyncStorage.getItem(PENDING_KEY);
  if (raw === null) {
    return [];
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as string[]) : [];
  } catch {
    return [];
  }
}

export async function queueCrossOff(itemId: string): Promise<void> {
  const pending = await loadPendingCrossOffs();
  if (!pending.includes(itemId)) {
    pending.push(itemId);
  }
  await AsyncStorage.setItem(PENDING_KEY, JSON.stringify(pending));
}

export async function removePendingCrossOff(itemId: string): Promise<void> {
  const pending = await loadPendingCrossOffs();
  await AsyncStorage.setItem(
    PENDING_KEY,
    JSON.stringify(pending.filter((id) => id !== itemId)),
  );
}
