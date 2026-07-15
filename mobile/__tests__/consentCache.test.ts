import AsyncStorage from "@react-native-async-storage/async-storage";

jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

import { loadCachedConsent, saveCachedConsent } from "../storage/consentCache";


beforeEach(async () => AsyncStorage.clear());

it("caches reusable session consent and clears single-image consent", async () => {
  await saveCachedConsent("session", "session-1");
  expect(await loadCachedConsent()).toEqual({ choice: "session", shoppingSessionId: "session-1" });

  await saveCachedConsent("answer_only", "session-1");
  expect(await loadCachedConsent()).toBeNull();
});
