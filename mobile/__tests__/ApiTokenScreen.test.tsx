import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { ApiTokenScreen } from "../screens/ApiTokenScreen";


it("stores a valid credential and never renders its value", async () => {
  const saveToken = jest.fn().mockResolvedValue(undefined);
  await render(<ApiTokenScreen saveToken={saveToken} />);
  const input = screen.getByLabelText("PantryOps API credential");
  const button = screen.getByRole("button", { name: "Save API credential" });

  await fireEvent.changeText(input, "a-secure-personal-token-with-32-characters");
  await fireEvent.press(button);

  await waitFor(() => expect(saveToken).toHaveBeenCalledWith("a-secure-personal-token-with-32-characters"));
  expect(screen.getByText("API credential saved securely on this device")).toBeTruthy();
  expect(input.props.value).toBe("");
});


it("rejects short credentials before storage", async () => {
  const saveToken = jest.fn();
  await render(<ApiTokenScreen saveToken={saveToken} />);
  const button = screen.getByRole("button", { name: "Save API credential" });

  await fireEvent.changeText(screen.getByLabelText("PantryOps API credential"), "short");

  expect(button.props.accessibilityState.disabled).toBe(true);
  expect(saveToken).not.toHaveBeenCalled();
});
