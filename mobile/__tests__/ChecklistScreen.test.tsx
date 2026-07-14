import React from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { fireEvent, render, screen } from "@testing-library/react-native";

jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
jest.mock("../api/client", () => ({
  confirmShoppingItem: jest.fn(),
}));

import { confirmShoppingItem } from "../api/client";
import { ChecklistScreen } from "../screens/ChecklistScreen";
import {
  loadPendingCrossOffs,
  saveChecklist,
  queueCrossOff,
} from "../storage/checklistCache";

const confirmMock = confirmShoppingItem as jest.Mock;

const ITEMS = [
  { id: "item-milk", name: "milk", category: "dairy", checked: false },
  { id: "item-rice", name: "rice", category: "grains", checked: false },
];

describe("ChecklistScreen", () => {
  beforeEach(async () => {
    await AsyncStorage.clear();
    confirmMock.mockReset();
    await saveChecklist(ITEMS);
  });

  it("renders items grouped by category with accessible checkboxes", async () => {
    await render(<ChecklistScreen listId="list-1" />);
    expect(await screen.findByRole("header", { name: "dairy" })).toBeTruthy();
    expect(screen.getByRole("header", { name: "grains" })).toBeTruthy();
    const milk = screen.getByRole("checkbox", { name: "Cross off milk" });
    expect(milk.props.accessibilityState.checked).toBe(false);
    expect(screen.getByRole("checkbox", { name: "Cross off rice" })).toBeTruthy();
  });

  it("cross-off while offline queues and survives reload", async () => {
    confirmMock.mockRejectedValue(new Error("network down"));
    await render(<ChecklistScreen listId="list-1" />);
    await fireEvent.press(
      await screen.findByRole("checkbox", { name: "Cross off milk" }),
    );
    expect(await screen.findByText(/pending sync/i)).toBeTruthy();
    expect(await loadPendingCrossOffs()).toContain("item-milk");

    await screen.unmount();
    await render(<ChecklistScreen listId="list-1" />);
    expect(await screen.findByText(/pending sync/i)).toBeTruthy();
  });

  it("syncs queued cross-offs when back online", async () => {
    await saveChecklist([
      { ...ITEMS[0], checked: true },
      ITEMS[1],
    ]);
    await queueCrossOff("item-milk");
    confirmMock.mockResolvedValue({ ok: true, pantryItemId: "p-1" });

    await render(<ChecklistScreen listId="list-1" />);
    await fireEvent.press(
      await screen.findByRole("button", { name: "Sync pending cross-offs" }),
    );

    expect(await screen.findByText(/bought/i)).toBeTruthy();
    expect(await loadPendingCrossOffs()).toEqual([]);
    expect(confirmMock).toHaveBeenCalledWith("list-1", "item-milk");
  });

  it("crossed-off items remain readable", async () => {
    confirmMock.mockResolvedValue({ ok: true, pantryItemId: "p-1" });
    await render(<ChecklistScreen listId="list-1" />);
    await fireEvent.press(
      await screen.findByRole("checkbox", { name: "Cross off milk" }),
    );
    // name still present and state conveyed by text, not styling alone
    expect(await screen.findByText(/bought/i)).toBeTruthy();
    expect(screen.getByText("milk")).toBeTruthy();
    const milk = screen.getByRole("checkbox", { name: "Cross off milk" });
    expect(milk.props.accessibilityState.checked).toBe(true);
  });
});
