import AsyncStorage from "@react-native-async-storage/async-storage";

import type { ConsentChoice } from "../api/client";

const KEY = "pantryops:image-consent";

export type CachedConsent = {
  choice: Exclude<ConsentChoice, "answer_only">;
  shoppingSessionId: string | null;
};

export async function loadCachedConsent(): Promise<CachedConsent | null> {
  const raw = await AsyncStorage.getItem(KEY);
  return raw ? (JSON.parse(raw) as CachedConsent) : null;
}

export async function saveCachedConsent(
  choice: ConsentChoice,
  shoppingSessionId: string,
): Promise<void> {
  if (choice === "answer_only") {
    await AsyncStorage.removeItem(KEY);
    return;
  }
  await AsyncStorage.setItem(
    KEY,
    JSON.stringify({
      choice,
      shoppingSessionId: choice === "session" ? shoppingSessionId : null,
    } satisfies CachedConsent),
  );
}
