import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY = "checklist.v1";

export type ChecklistItem = {
  id: string;
  name: string;
  checked: boolean;
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
