import React from "react";
import { fireEvent, render, screen } from "@testing-library/react-native";

const mockPush = jest.fn();
const mockParams = jest.fn();

jest.mock("expo-router", () => ({
  useLocalSearchParams: () => mockParams(),
  useRouter: () => ({ push: mockPush }),
}));

jest.mock("../screens/ChecklistScreen", () => {
  const { Pressable, Text } = require("react-native");
  return {
    ChecklistScreen: ({
      listId,
      onFinishShopping,
    }: {
      listId: string;
      onFinishShopping: (activeListId: string) => void;
    }) => (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Mock finish shopping"
        onPress={() => onFinishShopping(listId)}
      >
        <Text>{listId}</Text>
      </Pressable>
    ),
  };
});

jest.mock("../screens/CheckInScreen", () => {
  const { Text } = require("react-native");
  return {
    CheckInScreen: ({ shoppingListLabel }: { shoppingListLabel?: string }) => (
      <Text>{shoppingListLabel ?? "No shopping context"}</Text>
    ),
  };
});

import CheckInRoute from "../app/check-in";
import ShoppingRoute from "../app/shopping";

beforeEach(() => {
  mockPush.mockReset();
  mockParams.mockReset();
});

it("routes the active shopping list to check-in as navigation context only", async () => {
  mockParams.mockReturnValue({ listId: "list-1", label: "Saturday run" });
  await render(<ShoppingRoute />);

  await fireEvent.press(screen.getByRole("button", { name: "Mock finish shopping" }));

  expect(mockPush).toHaveBeenCalledWith({
    pathname: "/check-in",
    params: { shoppingListLabel: "Saturday run" },
  });
  expect(mockPush.mock.calls[0][0].params).not.toHaveProperty("shoppingSessionId");
});

it("shows shopping context passed to the production check-in route", async () => {
  mockParams.mockReturnValue({ shoppingListLabel: "Saturday run" });
  await render(<CheckInRoute />);

  expect(screen.getByText("Saturday run")).toBeTruthy();
});

it("rejects a shopping route without an active list id", async () => {
  mockParams.mockReturnValue({});
  await render(<ShoppingRoute />);

  expect(screen.getByText("Open a shopping list before starting the checklist.")).toBeTruthy();
});
