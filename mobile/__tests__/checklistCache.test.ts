import AsyncStorage from "@react-native-async-storage/async-storage";

import {
  clearChecklist,
  loadChecklist,
  saveChecklist,
} from "../storage/checklistCache";

jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

const SAMPLE = [
  { id: "item-1", name: "Milk", checked: false },
  { id: "item-2", name: "Rice", checked: true },
];

describe("checklistCache", () => {
  beforeEach(async () => {
    await AsyncStorage.clear();
  });

  it("round-trips a saved checklist", async () => {
    await saveChecklist(SAMPLE);
    expect(await loadChecklist()).toEqual(SAMPLE);
  });

  it("returns null when storage is empty", async () => {
    expect(await loadChecklist()).toBeNull();
  });

  it("clears the checklist", async () => {
    await saveChecklist(SAMPLE);
    await clearChecklist();
    expect(await loadChecklist()).toBeNull();
  });

  it("returns null on corrupted JSON instead of throwing", async () => {
    await AsyncStorage.setItem("checklist.v1", "{not json!");
    expect(await loadChecklist()).toBeNull();
  });
});
